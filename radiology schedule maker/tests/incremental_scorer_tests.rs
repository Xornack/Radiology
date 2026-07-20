use radiology_schedule_maker::models::*;
use radiology_schedule_maker::solver::constraints::HardConstraintChecker;
use radiology_schedule_maker::solver::cost::calculate_soft_cost;
use radiology_schedule_maker::solver::engine::ScheduleSolver;
use radiology_schedule_maker::solver::incremental::IncrementalScorer;
use rand::Rng;

#[test]
fn incremental_scorer_matches_full_rescan_after_random_moves() {
    let rads = default_radiologists();
    let svcs = default_services();
    let vacs: Vec<VacationRequest> = vec![VacationRequest::new("v1", "rad_mh", "2026-07-05", "Conference")];

    let holidays: Vec<Holiday> = vec![];
    let solver = ScheduleSolver::new(&rads, &svcs, &vacs, &holidays);
    let mut schedule = solver.create_empty_schedule(2026, 7, 31);
    solver.initialize_greedy(&mut schedule);

    let checker = HardConstraintChecker::new(&rads, &svcs, &vacs);
    let mut scorer = IncrementalScorer::new(&schedule.slots, &rads, &svcs, &checker);

    let full_violations = checker.count_violations(&schedule.slots) as i64;
    let full_cost = calculate_soft_cost(&schedule.slots, &rads, &svcs);
    assert_eq!(scorer.total_violations, full_violations, "violations mismatch at t=0");
    assert!((scorer.total_cost - full_cost).abs() < 1e-6, "cost mismatch at t=0: {} vs {}", scorer.total_cost, full_cost);

    let mut rng = rand::thread_rng();
    for i in 0..500 {
        let idx = rng.gen_range(0..schedule.slots.len());
        let date = schedule.slots[idx].date.clone();
        let service_id = schedule.slots[idx].service_id.clone();
        let old_rad = schedule.slots[idx].assigned_radiologist_id.clone();

        let candidates: Vec<Option<String>> = std::iter::once(None)
            .chain(rads.iter().filter(|r| checker.can_assign(&r.id, &service_id, &date)).map(|r| Some(r.id.clone())))
            .collect();
        let new_rad = candidates[rng.gen_range(0..candidates.len())].clone();

        scorer.apply_move(&checker, &date, &service_id, &old_rad, &new_rad);
        schedule.slots[idx].assigned_radiologist_id = new_rad;

        let full_violations = checker.count_violations(&schedule.slots) as i64;
        let full_cost = calculate_soft_cost(&schedule.slots, &rads, &svcs);
        assert_eq!(scorer.total_violations, full_violations, "violations mismatch at move {}", i);
        assert!(
            (scorer.total_cost - full_cost).abs() < 1e-6,
            "cost mismatch at move {}: incremental={} full={}", i, scorer.total_cost, full_cost
        );
    }
}

#[test]
fn optional_service_unassigned_slot_does_not_incur_penalty() {
    let mut svcs = default_services();
    // Make FLOAT optional, so an unfilled float slot shouldn't cost anything.
    if let Some(float) = svcs.iter_mut().find(|s| s.id == "float") {
        float.required = false;
    }
    let rads = default_radiologists();
    let vacs: Vec<VacationRequest> = vec![];
    let holidays: Vec<Holiday> = vec![];

    let solver = ScheduleSolver::new(&rads, &svcs, &vacs, &holidays);
    let mut schedule = solver.create_empty_schedule(2026, 7, 31);
    // Leave everything unassigned.
    let checker = HardConstraintChecker::new(&rads, &svcs, &vacs);

    let full_cost = calculate_soft_cost(&schedule.slots, &rads, &svcs);
    let scorer = IncrementalScorer::new(&schedule.slots, &rads, &svcs, &checker);
    assert!((scorer.total_cost - full_cost).abs() < 1e-6);

    // A required service's unfilled slot must still cost UNASSIGNED_PENALTY;
    // float's must not. Spot check by comparing against a schedule where
    // float is required too.
    if let Some(float) = svcs.iter_mut().find(|s| s.id == "float") {
        float.required = true;
    }
    let cost_with_float_required = calculate_soft_cost(&schedule.slots, &rads, &svcs);
    assert!(cost_with_float_required > full_cost, "marking float required should raise the cost");
}
