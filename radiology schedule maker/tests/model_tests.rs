use radiology_schedule_maker::models::*;

#[test]
fn derive_initials_two_words_ascii() {
    assert_eq!(derive_initials("Matt Harwood"), "MH");
}

#[test]
fn derive_initials_single_word_returns_first_letter_only() {
    assert_eq!(derive_initials("Cher"), "C");
}

#[test]
fn derive_initials_handles_non_ascii_first_letter() {
    assert_eq!(derive_initials("Émile Zola"), "ÉZ");
}

#[test]
fn display_badge_falls_back_to_full_name_for_single_word() {
    let rad = Radiologist::new("r1", "Cher", "", vec!["ALL"], true);
    assert_eq!(rad.display_badge(), "Cher");
}

#[test]
fn display_badge_uses_explicit_initials_when_set() {
    let rad = Radiologist::new("r1", "Matt Harwood", "MH", vec!["ALL"], true);
    assert_eq!(rad.display_badge(), "MH");
}

#[test]
fn display_badge_derives_from_non_ascii_name_without_panicking() {
    let rad = Radiologist::new("r1", "Émile Zola", "", vec!["ALL"], true);
    assert_eq!(rad.display_badge(), "ÉZ");
}

#[test]
fn next_radiologist_id_skips_ids_already_in_use() {
    let mut rads = default_radiologists();
    rads.push(Radiologist::new("rad_19", "Dr. Nineteen", "N1", vec!["ALL"], true));
    rads.push(Radiologist::new("rad_20", "Dr. Twenty", "T2", vec!["ALL"], true));
    rads.retain(|r| r.id != "rad_19"); // simulate: added two, then removed the older one

    let id = next_radiologist_id(&rads);
    assert_ne!(id, "rad_20", "must not collide with the surviving rad_20");
    assert!(!rads.iter().any(|r| r.id == id));
}

#[test]
fn vacation_id_differs_across_months_for_the_same_day_and_radiologist() {
    let july = vacation_id("rad_mh", 2026, 7, 5);
    let august = vacation_id("rad_mh", 2026, 8, 5);
    assert_ne!(july, august);
}

#[test]
fn clear_assignments_for_unassigns_only_the_matching_radiologist() {
    let mut sched = MonthlySchedule::new(2026, 7);
    let mut slot_a = ScheduleSlot::new("2026-07-01", 1, "msk");
    slot_a.assigned_radiologist_id = Some("rad_mh".to_string());
    let mut slot_b = ScheduleSlot::new("2026-07-01", 1, "abd");
    slot_b.assigned_radiologist_id = Some("rad_sbo".to_string());
    sched.slots = vec![slot_a, slot_b];

    sched.clear_assignments_for("rad_mh");

    assert_eq!(sched.slots[0].assigned_radiologist_id, None);
    assert_eq!(sched.slots[1].assigned_radiologist_id, Some("rad_sbo".to_string()));
}

#[test]
fn default_services_have_cadence_matching_shift_vs_call_category() {
    let svcs = default_services();
    let am_readout = svcs.iter().find(|s| s.id == "am_readout").unwrap();
    assert_eq!(am_readout.cadence, ServiceCadence::Weekdays);
    assert!(am_readout.required);

    let trauma_call = svcs.iter().find(|s| s.id == "trauma_call").unwrap();
    assert_eq!(trauma_call.cadence, ServiceCadence::Weekends);
    assert!(trauma_call.required);
}
