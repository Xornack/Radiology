use radiology_schedule_maker::utils::calendar::week_day_range;

#[test]
fn week_day_range_clamps_final_week_to_month_length() {
    assert_eq!(week_day_range(1, 31), Some((1, 7)));
    assert_eq!(week_day_range(5, 31), Some((29, 31)));
}

#[test]
fn week_day_range_none_when_week_does_not_exist_in_a_short_month() {
    assert_eq!(week_day_range(5, 28), None); // February, non-leap year
}

#[test]
fn week_day_range_handles_29_day_february() {
    assert_eq!(week_day_range(5, 29), Some((29, 29)));
}
