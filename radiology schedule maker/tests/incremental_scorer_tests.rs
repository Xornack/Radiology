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

    let solver = ScheduleSolver::new(&rads, &svcs, &vacs);
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
