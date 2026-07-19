use chrono::{Datelike, NaiveDate, Weekday};

/// Returns the exact number of days in a given year and month (handles leap years)
pub fn days_in_month(year: i32, month: u32) -> u32 {
    match month {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        2 => {
            if (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0) {
                29
            } else {
                28
            }
        }
        _ => 31,
    }
}

/// Returns short weekday abbreviation (Mon, Tue, Wed, Thu, Fri, Sat, Sun)
pub fn weekday_short_name(year: i32, month: u32, day: u32) -> &'static str {
    if let Some(date) = NaiveDate::from_ymd_opt(year, month, day) {
        match date.weekday() {
            Weekday::Mon => "Mon",
            Weekday::Tue => "Tue",
            Weekday::Wed => "Wed",
            Weekday::Thu => "Thu",
            Weekday::Fri => "Fri",
            Weekday::Sat => "Sat",
            Weekday::Sun => "Sun",
        }
    } else {
        "Day"
    }
}

/// Returns true if the date falls on a Saturday or Sunday
pub fn is_weekend_date(year: i32, month: u32, day: u32) -> bool {
    if let Some(date) = NaiveDate::from_ymd_opt(year, month, day) {
        matches!(date.weekday(), Weekday::Sat | Weekday::Sun)
    } else {
        false
    }
}

/// The (start, end) day-of-month range for a 1-indexed week number
/// (1..=5), clamped to `max_days`. Returns `None` if that week doesn't
/// exist in a month this short (e.g. week 5 in a 28-day February).
pub fn week_day_range(week: u32, max_days: u32) -> Option<(u32, u32)> {
    let start = match week {
        1 => 1,
        2 => 8,
        3 => 15,
        4 => 22,
        _ => 29,
    };
    if start > max_days {
        return None;
    }
    Some((start, (start + 6).min(max_days)))
}
