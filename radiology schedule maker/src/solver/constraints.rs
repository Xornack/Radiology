use crate::models::{Radiologist, ScheduleSlot, Service, VacationRequest};
use std::collections::{HashMap, HashSet};

pub struct HardConstraintChecker<'a> {
    pub radiologists: &'a [Radiologist],
    pub services: &'a [Service],
    pub vacations: &'a [VacationRequest],
    pub rad_map: HashMap<&'a str, &'a Radiologist>,
    pub service_map: HashMap<&'a str, &'a Service>,
    pub pto_set: HashSet<(&'a str, &'a str)>, // (radiologist_id, date)
}

impl<'a> HardConstraintChecker<'a> {
    pub fn new(
        radiologists: &'a [Radiologist],
        services: &'a [Service],
        vacations: &'a [VacationRequest],
    ) -> Self {
        let rad_map = radiologists.iter().map(|r| (r.id.as_str(), r)).collect();
        let service_map = services.iter().map(|s| (s.id.as_str(), s)).collect();
        let pto_set = vacations
            .iter()
            .map(|v| (v.radiologist_id.as_str(), v.date.as_str()))
            .collect();

        Self {
            radiologists,
            services,
            vacations,
            rad_map,
            service_map,
            pto_set,
        }
    }

    /// Checks if a radiologist can be assigned to a specific slot on a date
    pub fn can_assign(&self, rad_id: &str, service_id: &str, date: &str) -> bool {
        // 1. Check PTO blackout
        if self.pto_set.contains(&(rad_id, date)) {
            return false;
        }

        // 2. Check Radiologist Capability
        if let Some(rad) = self.rad_map.get(rad_id) {
            if let Some(svc) = self.service_map.get(service_id) {
                // If it's a call service, check call eligibility
                if (svc.is_night_call || svc.is_weekend)
                    && !rad.can_cover_call {
                        return false;
                    }
                // Check service qualification
                if !rad.covers_service(service_id) {
                    return false;
                }
            } else {
                return false;
            }
        } else {
            return false;
        }

        true
    }

    /// Evaluates total hard constraint violations in a set of slots
    pub fn count_violations(&self, slots: &[ScheduleSlot]) -> u32 {
        let mut violations = 0;

        // Group assignments by (date, rad_id) to check multi-service concurrency
        let mut daily_assignments: HashMap<(&str, &str), Vec<&str>> = HashMap::new();

        for slot in slots {
            if let Some(ref rad_id) = slot.assigned_radiologist_id {
                // Check individual assignment validity
                if !self.can_assign(rad_id, &slot.service_id, &slot.date) {
                    violations += 1;
                }

                daily_assignments
                    .entry((&slot.date, rad_id.as_str()))
                    .or_default()
                    .push(&slot.service_id);
            }
        }

        // Check daily concurrency & bundle compatibility
        for ((_date, _rad_id), service_ids) in daily_assignments {
            if service_ids.len() > 1 {
                // If more than 1 service assigned on the same day, verify compatibility
                for i in 0..service_ids.len() {
                    for j in (i + 1)..service_ids.len() {
                        let s1 = service_ids[i];
                        let s2 = service_ids[j];

                        let compatible = self
                            .service_map
                            .get(s1)
                            .and_then(|svc| svc.bundled_with.as_deref()) == Some(s2);

                        if !compatible {
                            violations += 1; // Incompatible double coverage
                        }
                    }
                }
            }
        }

        violations
    }
}
