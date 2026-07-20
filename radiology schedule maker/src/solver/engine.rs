use crate::models::{Holiday, MonthlySchedule, Radiologist, ScheduleSlot, Service, ServiceCadence, VacationRequest};
use crate::solver::constraints::HardConstraintChecker;
use crate::solver::cost::calculate_soft_cost;
use crate::solver::incremental::IncrementalScorer;
use crate::utils::calendar::is_weekend_or_holiday;
use rand::Rng;
use std::collections::HashSet;

pub struct ScheduleSolver<'a> {
    pub radiologists: &'a [Radiologist],
    pub services: &'a [Service],
    pub vacations: &'a [VacationRequest],
    pub holidays: &'a [Holiday],
}

impl<'a> ScheduleSolver<'a> {
    pub fn new(
        radiologists: &'a [Radiologist],
        services: &'a [Service],
        vacations: &'a [VacationRequest],
        holidays: &'a [Holiday],
    ) -> Self {
        Self {
            radiologists,
            services,
            vacations,
            holidays,
        }
    }

    /// Whether `service`'s cadence calls for a slot on the given day
    /// (holidays count as weekend days for this purpose -- see
    /// is_weekend_or_holiday). Shared by create_empty_schedule and
    /// reconcile_slots so the cadence match logic lives in one place.
    fn is_slot_desired(&self, year: i32, month: u32, day: u32, service: &Service) -> bool {
        let weekend_like = is_weekend_or_holiday(year, month, day, self.holidays);
        match service.cadence {
            ServiceCadence::AllDays => true,
            ServiceCadence::Weekdays => !weekend_like,
            ServiceCadence::Weekends => weekend_like,
        }
    }

    /// Initializes an empty month schedule, creating a slot for each
    /// service on each day its cadence calls for (holidays count as
    /// weekend days for this purpose -- see is_weekend_or_holiday).
    pub fn create_empty_schedule(&self, year: i32, month: u32, days_in_month: u32) -> MonthlySchedule {
        let mut schedule = MonthlySchedule::new(year, month);

        for day in 1..=days_in_month {
            let date = format!("{:04}-{:02}-{:02}", year, month, day);
            for svc in self.services {
                if self.is_slot_desired(year, month, day, svc) {
                    schedule.slots.push(ScheduleSlot::new(&date, day, &svc.id));
                }
            }
        }

        schedule
    }

    /// Adds slots for (day, service) pairs the current cadence/holiday rules
    /// now call for but the schedule doesn't have yet, and removes slots
    /// whose service was deleted or whose cadence no longer includes that
    /// day. Every surviving slot's assignment and lock are left byte-for-
    /// byte untouched -- but a slot CAN be dropped entirely (assignment and
    /// lock included) if a holiday or cadence change makes it no longer
    /// desired, e.g. locking a weekday rotation then marking that day a
    /// holiday will drop that lock along with the slot. This is what lets
    /// adding/removing a rotation or holiday reach an already-generated
    /// month without discarding UNRELATED manual work, unlike
    /// create_empty_schedule which always starts from nothing.
    pub fn reconcile_slots(&self, schedule: &mut MonthlySchedule) {
        let year = schedule.year;
        let month = schedule.month;
        let total_days = crate::utils::calendar::days_in_month(year, month);

        schedule.slots.retain(|s| {
            self.services
                .iter()
                .find(|svc| svc.id == s.service_id)
                .map(|svc| self.is_slot_desired(year, month, s.day_number, svc))
                .unwrap_or(false)
        });

        let existing: HashSet<(String, u32)> = schedule
            .slots
            .iter()
            .map(|s| (s.service_id.clone(), s.day_number))
            .collect();

        let mut to_add = Vec::new();
        for day in 1..=total_days {
            let date = format!("{:04}-{:02}-{:02}", year, month, day);
            for svc in self.services {
                if !existing.contains(&(svc.id.clone(), day)) && self.is_slot_desired(year, month, day, svc) {
                    to_add.push(ScheduleSlot::new(&date, day, &svc.id));
                }
            }
        }
        schedule.slots.extend(to_add);

        // Restore day-major order: EmailModal's digest generator assumes
        // slots are grouped by day_number (it prints a new "Day X" header
        // whenever day_number changes from the previous slot), and the
        // retain+extend above can leave newly-added slots out of order.
        schedule.slots.sort_by_key(|s| s.day_number);
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
        let mut scorer = IncrementalScorer::new(&current_slots, self.radiologists, self.services, &checker);
        let mut current_total_score = (scorer.total_violations as f64) * 1000.0 + scorer.total_cost;

        let mut best_slots = current_slots.clone();
        let mut best_score = current_total_score;
        let mut best_violations = scorer.total_violations;

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

            let idx = unlocked_indices[rng.gen_range(0..unlocked_indices.len())];
            let date = current_slots[idx].date.clone();
            let service_id = current_slots[idx].service_id.clone();
            let old_assignment = current_slots[idx].assigned_radiologist_id.clone();

            let mut candidate_rad_ids: Vec<Option<String>> = vec![None];
            for rad in self.radiologists {
                if checker.can_assign(&rad.id, &service_id, &date) {
                    candidate_rad_ids.push(Some(rad.id.clone()));
                }
            }

            let new_pick = candidate_rad_ids[rng.gen_range(0..candidate_rad_ids.len())].clone();

            scorer.apply_move(&checker, &date, &service_id, &old_assignment, &new_pick);
            current_slots[idx].assigned_radiologist_id = new_pick.clone();

            let new_total_score = (scorer.total_violations as f64) * 1000.0 + scorer.total_cost;
            let delta = new_total_score - current_total_score;

            // Metropolis acceptance criterion
            if delta < 0.0 || ((-delta / temp).exp() > rng.gen::<f64>()) {
                current_total_score = new_total_score;

                if current_total_score < best_score {
                    best_score = current_total_score;
                    best_slots = current_slots.clone();
                    best_violations = scorer.total_violations;
                }
            } else {
                // Revert move, in both the slot array and the scorer's running stats.
                scorer.apply_move(&checker, &date, &service_id, &new_pick, &old_assignment);
                current_slots[idx].assigned_radiologist_id = old_assignment;
            }
        }

        // Apply best solution found
        schedule.slots = best_slots;
        schedule.hard_violations = best_violations as u32;
        schedule.score = calculate_soft_cost(&schedule.slots, self.radiologists, self.services);
    }
}
