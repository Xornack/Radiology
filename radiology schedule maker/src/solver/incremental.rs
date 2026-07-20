use crate::models::{Radiologist, Service, ScheduleSlot};
use crate::solver::constraints::HardConstraintChecker;
use crate::solver::cost::{CALL_FAIRNESS_WEIGHT, TARGET_VARIANCE_WEIGHT, UNASSIGNED_PENALTY};
use std::collections::HashMap;

/// Running sufficient statistics for the solver's hot loop. Lets a single
/// slot mutation be scored in time proportional to the number of other
/// assignments sharing that slot's date, instead of rescanning every slot
/// in the schedule on every iteration (which is what made 6000 simulated-
/// annealing iterations take over a second before this was introduced).
pub struct IncrementalScorer<'a> {
    service_map: HashMap<&'a str, &'a Service>,
    targets: HashMap<&'a str, f64>,
    call_eligible_ids: Vec<&'a str>,

    shift_counts: HashMap<String, u32>,
    weekend_counts: HashMap<String, u32>,
    daily_assignments: HashMap<(String, String), Vec<String>>, // (date, rad_id) -> service_ids assigned that day

    unassigned_count: i64,
    target_variance_cost: f64,
    call_sum: f64,
    call_sum_sq: f64,

    pub total_violations: i64,
    pub total_cost: f64,
}

impl<'a> IncrementalScorer<'a> {
    pub fn new(
        slots: &[ScheduleSlot],
        radiologists: &'a [Radiologist],
        services: &'a [Service],
        checker: &HardConstraintChecker,
    ) -> Self {
        let service_map: HashMap<&str, &Service> = services.iter().map(|s| (s.id.as_str(), s)).collect();
        let targets: HashMap<&str, f64> = radiologists.iter().map(|r| (r.id.as_str(), r.target_monthly_shifts as f64)).collect();
        let call_eligible_ids: Vec<&str> = radiologists.iter().filter(|r| r.can_cover_call).map(|r| r.id.as_str()).collect();

        let mut shift_counts: HashMap<String, u32> = HashMap::new();
        let mut weekend_counts: HashMap<String, u32> = HashMap::new();
        let mut daily_assignments: HashMap<(String, String), Vec<String>> = HashMap::new();
        let mut unassigned_count: i64 = 0;
        let mut total_violations: i64 = 0;

        for slot in slots {
            match &slot.assigned_radiologist_id {
                Some(rad_id) => {
                    *shift_counts.entry(rad_id.clone()).or_default() += 1;
                    if let Some(svc) = service_map.get(slot.service_id.as_str()) {
                        if svc.is_weekend || svc.is_night_call {
                            *weekend_counts.entry(rad_id.clone()).or_default() += 1;
                        }
                    }
                    daily_assignments
                        .entry((slot.date.clone(), rad_id.clone()))
                        .or_default()
                        .push(slot.service_id.clone());

                    if !checker.can_assign(rad_id, &slot.service_id, &slot.date) {
                        total_violations += 1;
                    }
                }
                None => {
                    let required = service_map.get(slot.service_id.as_str()).map(|s| s.required).unwrap_or(true);
                    if required {
                        unassigned_count += 1;
                    }
                }
            }
        }

        for ((_date, _rad), service_ids) in daily_assignments.iter() {
            for i in 0..service_ids.len() {
                for j in (i + 1)..service_ids.len() {
                    let compatible = service_map
                        .get(service_ids[i].as_str())
                        .and_then(|svc| svc.bundled_with.as_deref())
                        .is_some_and(|b| b == service_ids[j]);
                    if !compatible {
                        total_violations += 1;
                    }
                }
            }
        }

        let mut target_variance_cost = 0.0;
        for rad in radiologists {
            let assigned = *shift_counts.get(rad.id.as_str()).unwrap_or(&0) as f64;
            let target = *targets.get(rad.id.as_str()).unwrap_or(&0.0);
            let diff = assigned - target;
            target_variance_cost += diff * diff * TARGET_VARIANCE_WEIGHT;
        }

        let call_sum: f64 = call_eligible_ids.iter().map(|id| *weekend_counts.get(*id).unwrap_or(&0) as f64).sum();
        let call_sum_sq: f64 = call_eligible_ids.iter().map(|id| {
            let c = *weekend_counts.get(*id).unwrap_or(&0) as f64;
            c * c
        }).sum();

        let mut scorer = Self {
            service_map,
            targets,
            call_eligible_ids,
            shift_counts,
            weekend_counts,
            daily_assignments,
            unassigned_count,
            target_variance_cost,
            call_sum,
            call_sum_sq,
            total_violations,
            total_cost: 0.0,
        };
        scorer.total_cost = scorer.compute_total_cost();
        scorer
    }

    fn call_variance(&self) -> f64 {
        let n = self.call_eligible_ids.len() as f64;
        if n == 0.0 {
            return 0.0;
        }
        let mean = self.call_sum / n;
        (self.call_sum_sq / n) - (mean * mean)
    }

    fn compute_total_cost(&self) -> f64 {
        (self.unassigned_count as f64) * UNASSIGNED_PENALTY + self.target_variance_cost + self.call_variance() * CALL_FAIRNESS_WEIGHT
    }

    fn rad_target_contribution(&self, rad_id: &str) -> f64 {
        let assigned = *self.shift_counts.get(rad_id).unwrap_or(&0) as f64;
        let target = *self.targets.get(rad_id).unwrap_or(&0.0);
        let diff = assigned - target;
        diff * diff * TARGET_VARIANCE_WEIGHT
    }

    fn is_weekend_service(&self, service_id: &str) -> bool {
        self.service_map.get(service_id).map(|s| s.is_weekend || s.is_night_call).unwrap_or(false)
    }

    fn remove_assignment(&mut self, date: &str, service_id: &str, rad_id: &str) {
        self.target_variance_cost -= self.rad_target_contribution(rad_id);
        *self.shift_counts.entry(rad_id.to_string()).or_default() -= 1;
        self.target_variance_cost += self.rad_target_contribution(rad_id);

        if self.is_weekend_service(service_id) {
            if self.call_eligible_ids.contains(&rad_id) {
                let old = *self.weekend_counts.get(rad_id).unwrap_or(&0) as f64;
                self.call_sum -= old;
                self.call_sum_sq -= old * old;
            }
            let c = self.weekend_counts.entry(rad_id.to_string()).or_default();
            *c -= 1;
            if self.call_eligible_ids.contains(&rad_id) {
                let new = *c as f64;
                self.call_sum += new;
                self.call_sum_sq += new * new;
            }
        }

        if let Some(list) = self.daily_assignments.get_mut(&(date.to_string(), rad_id.to_string())) {
            if let Some(pos) = list.iter().position(|s| s == service_id) {
                list.remove(pos);
            }
        }
    }

    fn add_assignment(&mut self, date: &str, service_id: &str, rad_id: &str) {
        self.target_variance_cost -= self.rad_target_contribution(rad_id);
        *self.shift_counts.entry(rad_id.to_string()).or_default() += 1;
        self.target_variance_cost += self.rad_target_contribution(rad_id);

        if self.is_weekend_service(service_id) {
            if self.call_eligible_ids.contains(&rad_id) {
                let old = *self.weekend_counts.get(rad_id).unwrap_or(&0) as f64;
                self.call_sum -= old;
                self.call_sum_sq -= old * old;
            }
            let c = self.weekend_counts.entry(rad_id.to_string()).or_default();
            *c += 1;
            if self.call_eligible_ids.contains(&rad_id) {
                let new = *c as f64;
                self.call_sum += new;
                self.call_sum_sq += new * new;
            }
        }

        self.daily_assignments
            .entry((date.to_string(), rad_id.to_string()))
            .or_default()
            .push(service_id.to_string());
    }

    fn bundle_violation_count(&self, date: &str, rad_id: &str) -> i64 {
        let empty = Vec::new();
        let service_ids = self.daily_assignments.get(&(date.to_string(), rad_id.to_string())).unwrap_or(&empty);
        let mut v = 0i64;
        for i in 0..service_ids.len() {
            for j in (i + 1)..service_ids.len() {
                let compatible = self.service_map
                    .get(service_ids[i].as_str())
                    .and_then(|svc| svc.bundled_with.as_deref())
                    .is_some_and(|b| b == service_ids[j]);
                if !compatible {
                    v += 1;
                }
            }
        }
        v
    }

    /// Moves `service_id`'s assignment on `date` from `old_rad` to `new_rad`
    /// (either may be `None`) and updates `total_violations`/`total_cost` in
    /// place to match what `HardConstraintChecker::count_violations` and
    /// `calculate_soft_cost` would compute for the whole schedule.
    pub fn apply_move(
        &mut self,
        checker: &HardConstraintChecker,
        date: &str,
        service_id: &str,
        old_rad: &Option<String>,
        new_rad: &Option<String>,
    ) {
        let required = self.service_map.get(service_id).map(|s| s.required).unwrap_or(true);

        if let Some(old_id) = old_rad {
            if !checker.can_assign(old_id, service_id, date) {
                self.total_violations -= 1;
            }
            self.total_violations -= self.bundle_violation_count(date, old_id);
            self.remove_assignment(date, service_id, old_id);
            self.total_violations += self.bundle_violation_count(date, old_id);
            if required {
                self.unassigned_count += 1;
            }
        }

        if let Some(new_id) = new_rad {
            if required {
                self.unassigned_count -= 1;
            }
            self.total_violations -= self.bundle_violation_count(date, new_id);
            self.add_assignment(date, service_id, new_id);
            self.total_violations += self.bundle_violation_count(date, new_id);
            if !checker.can_assign(new_id, service_id, date) {
                self.total_violations += 1;
            }
        }

        self.total_cost = self.compute_total_cost();
    }
}
