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

use radiology_schedule_maker::models::Holiday;
use radiology_schedule_maker::utils::calendar::is_weekend_or_holiday;

#[test]
fn is_weekend_or_holiday_true_on_actual_weekend() {
    // 2026-07-04 is a Saturday
    assert!(is_weekend_or_holiday(2026, 7, 4, &[]));
}

#[test]
fn is_weekend_or_holiday_true_on_a_designated_holiday_weekday() {
    // 2026-07-03 is a Friday
    let holidays = vec![Holiday { id: "h1".into(), date: "2026-07-03".into(), name: "Summer Friday".into() }];
    assert!(is_weekend_or_holiday(2026, 7, 3, &holidays));
}

#[test]
fn is_weekend_or_holiday_false_on_an_ordinary_weekday() {
    assert!(!is_weekend_or_holiday(2026, 7, 8, &[])); // Wednesday, no holidays
}
