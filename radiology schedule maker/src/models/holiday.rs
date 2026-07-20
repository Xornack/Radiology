use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Holiday {
    pub id: String,
    pub date: String, // YYYY-MM-DD
    pub name: String,
}

/// Holiday id derived from the date itself, not a mutable list length, so
/// it's collision-safe by construction.
pub fn holiday_id(year: i32, month: u32, day: u32) -> String {
    format!("holiday_{:04}_{:02}_{:02}", year, month, day)
}
