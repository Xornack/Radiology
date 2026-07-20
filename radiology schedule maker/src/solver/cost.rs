use crate::models::{Radiologist, ScheduleSlot, Service};
use std::collections::HashMap;

pub const UNASSIGNED_PENALTY: f64 = 500.0;
pub const TARGET_VARIANCE_WEIGHT: f64 = 15.0;
pub const CALL_FAIRNESS_WEIGHT: f64 = 40.0;

pub fn calculate_soft_cost(
    slots: &[ScheduleSlot],
    radiologists: &[Radiologist],
    services: &[Service],
) -> f64 {
    let service_map: HashMap<&str, &Service> = services.iter().map(|s| (s.id.as_str(), s)).collect();
    let mut shift_counts: HashMap<&str, u32> = HashMap::new();
    let mut weekend_counts: HashMap<&str, u32> = HashMap::new();
    let mut unassigned_count = 0;

    for slot in slots {
        if let Some(ref rad_id) = slot.assigned_radiologist_id {
            *shift_counts.entry(rad_id.as_str()).or_default() += 1;

            if let Some(svc) = service_map.get(slot.service_id.as_str()) {
                if svc.is_weekend || svc.is_night_call {
                    *weekend_counts.entry(rad_id.as_str()).or_default() += 1;
                }
            }
        } else {
            let required = service_map.get(slot.service_id.as_str()).map(|s| s.required).unwrap_or(true);
            if required {
                unassigned_count += 1;
            }
        }
    }

    let mut total_cost = 0.0;

    // 1. Unassigned slots penalty (High priority soft constraint)
    total_cost += (unassigned_count as f64) * UNASSIGNED_PENALTY;

    // 2. Target shift variance penalty
    for rad in radiologists {
        let assigned = *shift_counts.get(rad.id.as_str()).unwrap_or(&0) as f64;
        let target = rad.target_monthly_shifts as f64;
        let diff = assigned - target;
        total_cost += diff * diff * TARGET_VARIANCE_WEIGHT; // Quadratic penalty for target deviation
    }

    // 3. Weekend / Call fairness equity penalty (Variance across call-eligible attendings)
    let call_rads: Vec<&Radiologist> = radiologists.iter().filter(|r| r.can_cover_call).collect();
    if !call_rads.is_empty() {
        let call_counts: Vec<f64> = call_rads
            .iter()
            .map(|r| *weekend_counts.get(r.id.as_str()).unwrap_or(&0) as f64)
            .collect();

        let mean = call_counts.iter().sum::<f64>() / (call_counts.len() as f64);
        let variance: f64 = call_counts.iter().map(|c| (c - mean).powi(2)).sum::<f64>() / (call_counts.len() as f64);
        
        total_cost += variance * CALL_FAIRNESS_WEIGHT; // Equity bonus for even weekend call distribution
    }

    total_cost
}
