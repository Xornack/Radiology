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
