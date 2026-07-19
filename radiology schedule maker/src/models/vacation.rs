use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct VacationRequest {
    pub id: String,
    pub radiologist_id: String,
    pub date: String, // ISO YYYY-MM-DD
    pub note: String,
}

impl VacationRequest {
    pub fn new(id: impl Into<String>, radiologist_id: impl Into<String>, date: impl Into<String>, note: impl Into<String>) -> Self {
        Self {
            id: id.into(),
            radiologist_id: radiologist_id.into(),
            date: date.into(),
            note: note.into(),
        }
    }
}

/// Vacation id derived from radiologist + full date, not just day-of-month,
/// so the same attending taking the same day off in two different months
/// doesn't produce two entries sharing one id (which makes deleting either
/// one delete both, since deletion filters by id).
pub fn vacation_id(radiologist_id: &str, year: i32, month: u32, day: u32) -> String {
    format!("v_{}_{:04}_{:02}_{:02}", radiologist_id, year, month, day)
}
