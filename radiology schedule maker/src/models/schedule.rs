use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ScheduleSlot {
    pub id: String,
    pub date: String,       // YYYY-MM-DD
    pub day_number: u32,    // 1..=31
    pub service_id: String,
    pub assigned_radiologist_id: Option<String>,
    pub is_locked: bool,
    pub has_pto_conflict: bool,
}

impl ScheduleSlot {
    pub fn new(date: impl Into<String>, day_number: u32, service_id: impl Into<String>) -> Self {
        let d = date.into();
        let s = service_id.into();
        let id = format!("{}_{}", d, s);
        Self {
            id,
            date: d,
            day_number,
            service_id: s,
            assigned_radiologist_id: None,
            is_locked: false,
            has_pto_conflict: false,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct MonthlySchedule {
    pub year: i32,
    pub month: u32,
    pub slots: Vec<ScheduleSlot>,
    pub score: f64,
    pub hard_violations: u32,
}

impl MonthlySchedule {
    pub fn new(year: i32, month: u32) -> Self {
        Self {
            year,
            month,
            slots: Vec::new(),
            score: 0.0,
            hard_violations: 0,
        }
    }

    /// Clears any slot assignment pointing at `radiologist_id`. Called when
    /// a radiologist is removed from the roster, so a deleted attending
    /// doesn't linger as a dangling, confusingly-styled grid assignment.
    pub fn clear_assignments_for(&mut self, radiologist_id: &str) {
        for slot in &mut self.slots {
            if slot.assigned_radiologist_id.as_deref() == Some(radiologist_id) {
                slot.assigned_radiologist_id = None;
            }
        }
    }
}
