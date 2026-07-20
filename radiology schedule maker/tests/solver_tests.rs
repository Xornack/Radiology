use radiology_schedule_maker::models::*;
use radiology_schedule_maker::solver::constraints::HardConstraintChecker;
use radiology_schedule_maker::solver::engine::ScheduleSolver;

#[test]
fn test_default_models_and_solver() {
    let rads = default_radiologists();
    let svcs = default_services();
    let vacs = vec![
        VacationRequest::new("v1", "rad_mh", "2026-07-05", "Conference"),
    ];

    let checker = HardConstraintChecker::new(&rads, &svcs, &vacs);

    // Dr. Matt Harwood (rad_mh) is on PTO on 2026-07-05 -> should return false
    assert!(!checker.can_assign("rad_mh", "msk", "2026-07-05"));

    // Dr. Matt Harwood is eligible on 2026-07-06 for MSK
    assert!(checker.can_assign("rad_mh", "msk", "2026-07-06"));

    // Dr. Matt Harwood only covers MSK / AM Readout, NOT ER -> should return false
    assert!(!checker.can_assign("rad_mh", "er", "2026-07-06"));

    // Test Solver Execution
    let holidays: Vec<Holiday> = vec![];
    let solver = ScheduleSolver::new(&rads, &svcs, &vacs, &holidays);
    let mut schedule = solver.create_empty_schedule(2026, 7, 31);
    solver.solve(&mut schedule, 1000);

    assert!(!schedule.slots.is_empty());

    // 2026-07-04 is a Saturday: a Weekdays-cadence service should have no slot there.
    assert!(!schedule.slots.iter().any(|s| s.service_id == "abd" && s.date == "2026-07-04"));
    // a Weekends-cadence service should.
    assert!(schedule.slots.iter().any(|s| s.service_id == "trauma_call" && s.date == "2026-07-04"));

    println!("Schedule solver test completed successfully. Score: {}", schedule.score);
}
