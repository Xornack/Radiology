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

#[test]
fn test_reconcile_slots_adds_new_service_without_disturbing_existing_assignments() {
    let rads = default_radiologists();
    let vacs: Vec<VacationRequest> = vec![];
    let holidays: Vec<Holiday> = vec![];

    let mut svcs = default_services();
    let solver = ScheduleSolver::new(&rads, &svcs, &vacs, &holidays);
    let mut schedule = solver.create_empty_schedule(2026, 7, 31);

    // Manually assign and lock an existing slot (2026-07-06 is a Monday, a
    // weekday, so the "abd" Weekdays-cadence service has a slot there).
    let target_id = "2026-07-06_abd".to_string();
    {
        let slot = schedule
            .slots
            .iter_mut()
            .find(|s| s.id == target_id)
            .expect("expected an 'abd' slot on 2026-07-06");
        slot.assigned_radiologist_id = Some("rad_sbo".to_string());
        slot.is_locked = true;
    }

    // Now add a brand-new required, AllDays-cadence service to the roster,
    // simulating a user adding a rotation via the Rotations tab.
    svcs.push(Service {
        id: "svc_extra_rotation".into(),
        name: "Extra Rotation".into(),
        category: ServiceCategory::ShiftCoverage,
        is_weekend: false,
        is_night_call: false,
        bundled_with: None,
        description: String::new(),
        cadence: ServiceCadence::AllDays,
        required: true,
    });

    let solver2 = ScheduleSolver::new(&rads, &svcs, &vacs, &holidays);
    solver2.reconcile_slots(&mut schedule);

    // The new service should now have a slot for every day of the month
    // (AllDays cadence, 31 days in July).
    let new_service_slots = schedule
        .slots
        .iter()
        .filter(|s| s.service_id == "svc_extra_rotation")
        .count();
    assert_eq!(new_service_slots, 31);

    // The pre-existing assignment/lock on the untouched "abd" slot must
    // survive reconciliation unchanged.
    let preserved = schedule
        .slots
        .iter()
        .find(|s| s.id == target_id)
        .expect("original 'abd' slot should still exist");
    assert_eq!(preserved.assigned_radiologist_id, Some("rad_sbo".to_string()));
    assert!(preserved.is_locked);

    // Slot ordering should stay day-major (EmailModal relies on this).
    let mut last_day = 0;
    for slot in &schedule.slots {
        assert!(slot.day_number >= last_day, "slots must stay sorted by day_number");
        last_day = slot.day_number;
    }
}

#[test]
fn test_reconcile_slots_removes_orphaned_service_slots() {
    let rads = default_radiologists();
    let vacs: Vec<VacationRequest> = vec![];
    let holidays: Vec<Holiday> = vec![];

    let mut svcs = default_services();
    let solver = ScheduleSolver::new(&rads, &svcs, &vacs, &holidays);
    let mut schedule = solver.create_empty_schedule(2026, 7, 31);
    assert!(schedule.slots.iter().any(|s| s.service_id == "abd"));

    // Simulate removing the "abd" rotation from the services list.
    svcs.retain(|s| s.id != "abd");

    let solver2 = ScheduleSolver::new(&rads, &svcs, &vacs, &holidays);
    solver2.reconcile_slots(&mut schedule);

    assert!(!schedule.slots.iter().any(|s| s.service_id == "abd"));
}
