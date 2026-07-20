use radiology_schedule_maker::models::*;
use radiology_schedule_maker::solver::constraints::HardConstraintChecker;
use radiology_schedule_maker::solver::cost::{calculate_soft_cost, UNASSIGNED_PENALTY};
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
    let schedule = solver.create_empty_schedule(2026, 7, 31);
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

// Directly exercises apply_move's `required`-gated branches (both the
// old-rad-removal and new-rad-addition sides), which the initial-scan test
// above never touches. Runs a matched pair of scorers -- one where FLOAT is
// required, one where it isn't -- through the exact same None->Some->None
// cycle via apply_move, and checks the UNASSIGNED_PENALTY gap between them
// opens, closes, and reopens exactly as expected with no drift.
#[test]
fn apply_move_on_optional_service_does_not_drift_unassigned_penalty() {
    let rads = default_radiologists();
    let vacs: Vec<VacationRequest> = vec![];
    let holidays: Vec<Holiday> = vec![];

    let mut optional_svcs = default_services();
    if let Some(float) = optional_svcs.iter_mut().find(|s| s.id == "float") {
        float.required = false;
    }
    let required_svcs = default_services(); // float stays required: true here

    // A single weekday (2026-07-01) so there's exactly one float slot --
    // keeps the UNASSIGNED_PENALTY-gap arithmetic below exact rather than
    // needing to account for however many float slots a full month has.
    let solver = ScheduleSolver::new(&rads, &optional_svcs, &vacs, &holidays);
    let schedule = solver.create_empty_schedule(2026, 7, 1);
    let checker = HardConstraintChecker::new(&rads, &optional_svcs, &vacs);

    let float_slot = schedule.slots.iter().find(|s| s.service_id == "float").expect("a float slot exists");
    let date = float_slot.date.clone();
    let service_id = "float".to_string();
    let rad_id = rads
        .iter()
        .find(|r| checker.can_assign(&r.id, &service_id, &date))
        .expect("some radiologist can cover float")
        .id
        .clone();

    let mut optional_scorer = IncrementalScorer::new(&schedule.slots, &rads, &optional_svcs, &checker);
    let mut required_scorer = IncrementalScorer::new(&schedule.slots, &rads, &required_svcs, &checker);

    // Unfilled: the optional scorer should be exactly UNASSIGNED_PENALTY
    // cheaper than the required one.
    assert!(
        (required_scorer.total_cost - optional_scorer.total_cost - UNASSIGNED_PENALTY).abs() < 1e-6,
        "unfilled optional slot should cost exactly UNASSIGNED_PENALTY less than a required one: required={} optional={}",
        required_scorer.total_cost, optional_scorer.total_cost
    );

    // Assign (None -> Some(rad_id)) on both. Once filled, whether the
    // service was "required" no longer matters -- costs should converge.
    optional_scorer.apply_move(&checker, &date, &service_id, &None, &Some(rad_id.clone()));
    required_scorer.apply_move(&checker, &date, &service_id, &None, &Some(rad_id.clone()));
    assert!(
        (required_scorer.total_cost - optional_scorer.total_cost).abs() < 1e-6,
        "once filled, the required flag should no longer affect cost: required={} optional={}",
        required_scorer.total_cost, optional_scorer.total_cost
    );

    // Unassign again (Some(rad_id) -> None). The UNASSIGNED_PENALTY gap
    // must reappear -- proving the removal branch re-applies the same gate.
    optional_scorer.apply_move(&checker, &date, &service_id, &Some(rad_id.clone()), &None);
    required_scorer.apply_move(&checker, &date, &service_id, &Some(rad_id.clone()), &None);
    assert!(
        (required_scorer.total_cost - optional_scorer.total_cost - UNASSIGNED_PENALTY).abs() < 1e-6,
        "after unassigning again, the UNASSIGNED_PENALTY gap must reappear with no drift: required={} optional={}",
        required_scorer.total_cost, optional_scorer.total_cost
    );

    // And the optional scorer's own cost after the full cycle must match a
    // fresh rescan exactly -- no state drift accumulated across the moves.
    let fresh_rescan = IncrementalScorer::new(&schedule.slots, &rads, &optional_svcs, &checker).total_cost;
    assert!(
        (optional_scorer.total_cost - fresh_rescan).abs() < 1e-6,
        "full assign/unassign cycle should return to the original cost with no drift: after_cycle={} fresh_rescan={}",
        optional_scorer.total_cost, fresh_rescan
    );
}
