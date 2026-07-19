use crate::models::{MonthlySchedule, Radiologist, ScheduleSlot, Service, VacationRequest};
use crate::solver::constraints::HardConstraintChecker;
use crate::solver::cost::calculate_soft_cost;
use rand::Rng;

pub struct ScheduleSolver<'a> {
    pub radiologists: &'a [Radiologist],
    pub services: &'a [Service],
    pub vacations: &'a [VacationRequest],
}

impl<'a> ScheduleSolver<'a> {
    pub fn new(
        radiologists: &'a [Radiologist],
        services: &'a [Service],
        vacations: &'a [VacationRequest],
    ) -> Self {
        Self {
            radiologists,
            services,
            vacations,
        }
    }

    /// Initializes a empty month schedule with all service slots
    pub fn create_empty_schedule(&self, year: i32, month: u32, days_in_month: u32) -> MonthlySchedule {
        let mut schedule = MonthlySchedule::new(year, month);

        for day in 1..=days_in_month {
            let date = format!("{:04}-{:02}-{:02}", year, month, day);
            for svc in self.services {
                // If it's a weekend service, only include on Saturday (6) / Sunday (7) or weekend tag
                let slot = ScheduleSlot::new(&date, day, &svc.id);
                schedule.slots.push(slot);
            }
        }

        schedule
    }

    /// Runs Greedy Constructive Initialization
    pub fn initialize_greedy(&self, schedule: &mut MonthlySchedule) {
        let checker = HardConstraintChecker::new(self.radiologists, self.services, self.vacations);
        let mut rng = rand::thread_rng();

        for slot in &mut schedule.slots {
            if slot.is_locked {
                continue;
            }

            // Find all candidate radiologists who satisfy hard constraints
            let candidates: Vec<&Radiologist> = self
                .radiologists
                .iter()
                .filter(|r| checker.can_assign(&r.id, &slot.service_id, &slot.date))
                .collect();

            if !candidates.is_empty() {
                let idx = rng.gen_range(0..candidates.len());
                slot.assigned_radiologist_id = Some(candidates[idx].id.clone());
            } else {
                slot.assigned_radiologist_id = None;
            }
        }

        schedule.hard_violations = checker.count_violations(&schedule.slots);
        schedule.score = calculate_soft_cost(&schedule.slots, self.radiologists, self.services);
    }

    /// Runs Simulated Annealing Optimization
    pub fn solve(&self, schedule: &mut MonthlySchedule, iterations: usize) {
        let checker = HardConstraintChecker::new(self.radiologists, self.services, self.vacations);
        let mut rng = rand::thread_rng();

        // 1. Initial greedy pass if unassigned
        if schedule.slots.iter().all(|s| s.assigned_radiologist_id.is_none()) {
            self.initialize_greedy(schedule);
        }

        let mut current_slots = schedule.slots.clone();
        let mut current_violations = checker.count_violations(&current_slots);
        let current_cost = calculate_soft_cost(&current_slots, self.radiologists, self.services);
        let mut current_total_score = (current_violations as f64) * 1000.0 + current_cost;

        let mut best_slots = current_slots.clone();
        let mut best_score = current_total_score;
        let mut best_violations = current_violations;

        let mut temp = 100.0;
        let cooling_rate = 0.9992;

        let unlocked_indices: Vec<usize> = current_slots
            .iter()
            .enumerate()
            .filter(|(_, s)| !s.is_locked)
            .map(|(i, _)| i)
            .collect();

        if unlocked_indices.is_empty() {
            return;
        }

        for _iter in 0..iterations {
            temp *= cooling_rate;

            // Pick a random unlocked slot to mutate
            let idx = unlocked_indices[rng.gen_range(0..unlocked_indices.len())];
            let old_assignment = current_slots[idx].assigned_radiologist_id.clone();

            // Either swap with another slot or reassign candidate
            let mut candidate_rad_ids: Vec<Option<String>> = vec![None];
            for rad in self.radiologists {
                if checker.can_assign(&rad.id, &current_slots[idx].service_id, &current_slots[idx].date) {
                    candidate_rad_ids.push(Some(rad.id.clone()));
                }
            }

            if candidate_rad_ids.is_empty() {
                continue;
            }

            let new_pick = &candidate_rad_ids[rng.gen_range(0..candidate_rad_ids.len())];
            current_slots[idx].assigned_radiologist_id = new_pick.clone();

            // Evaluate new state
            let new_violations = checker.count_violations(&current_slots);
            let new_cost = calculate_soft_cost(&current_slots, self.radiologists, self.services);
            let new_total_score = (new_violations as f64) * 1000.0 + new_cost;

            let delta = new_total_score - current_total_score;

            // Metropolis acceptance criterion
            if delta < 0.0 || ((-delta / temp).exp() > rng.gen::<f64>()) {
                // Accept move
                current_violations = new_violations;
                current_total_score = new_total_score;

                if current_total_score < best_score {
                    best_score = current_total_score;
                    best_slots = current_slots.clone();
                    best_violations = current_violations;
                }
            } else {
                // Revert move
                current_slots[idx].assigned_radiologist_id = old_assignment;
            }
        }

        // Apply best solution found
        schedule.slots = best_slots;
        schedule.hard_violations = best_violations;
        schedule.score = calculate_soft_cost(&schedule.slots, self.radiologists, self.services);
    }
}
