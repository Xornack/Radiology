use crate::components::*;
use crate::models::*;
use crate::solver::engine::ScheduleSolver;
use crate::utils::calendar::days_in_month;
use gloo_storage::{LocalStorage, Storage};
use leptos::prelude::*;

#[component]
pub fn App() -> impl IntoView {
    // 1. Core State Signals
    let (radiologists, set_radiologists) = signal(
        LocalStorage::get("radsched_radiologists").unwrap_or_else(|_| default_radiologists()),
    );

    let (services, _set_services) =
        signal(LocalStorage::get("radsched_services").unwrap_or_else(|_| default_services()));

    let (vacations, set_vacations) =
        signal(LocalStorage::get("radsched_vacations").unwrap_or_else(|_| vec![]));

    let (holidays, _set_holidays) = signal(Vec::<Holiday>::new());

    let (selected_year, set_selected_year) =
        signal(LocalStorage::get("radsched_selected_year").unwrap_or(2026i32));
    let (selected_month, set_selected_month) =
        signal(LocalStorage::get("radsched_selected_month").unwrap_or(7u32));

    let (schedule, set_schedule) = signal(
        LocalStorage::get("radsched_schedule")
            .unwrap_or_else(|_| MonthlySchedule::new(selected_year.get(), selected_month.get())),
    );

    let (active_tab, set_active_tab) = signal(ActiveTab::ScheduleGrid);
    let (selected_slot, set_selected_slot) = signal(None::<ScheduleSlot>);
    let (is_email_open, set_is_email_open) = signal(false);
    let (is_sheets_open, set_is_sheets_open) = signal(false);
    let (webhook_url, set_webhook_url) = signal(String::new());

    // 2. (Re)generate the schedule only when the viewed month/year actually
    // changes, or there's no usable schedule yet for it. Reading
    // radiologists/services/vacations with get_untracked() here is
    // deliberate: editing the roster, service list, or vacations must NOT
    // regenerate the schedule, or every lock/swap the scheduler made gets
    // silently discarded (this was the app's most severe bug).
    Effect::new(move |_| {
        let y = selected_year.get();
        let m = selected_month.get();

        let needs_new =
            schedule.with_untracked(|s| s.year != y || s.month != m || s.slots.is_empty());
        if !needs_new {
            return;
        }

        let rads = radiologists.get_untracked();
        let svcs = services.get_untracked();
        let vacs = vacations.get_untracked();
        let holis = holidays.get_untracked();

        let total_days = days_in_month(y, m);
        let solver = ScheduleSolver::new(&rads, &svcs, &vacs, &holis);
        let mut new_sched = solver.create_empty_schedule(y, m, total_days);
        solver.initialize_greedy(&mut new_sched);
        set_schedule.set(new_sched);
    });

    // LocalStorage persistence effects
    Effect::new(move |_| {
        let _ = LocalStorage::set("radsched_radiologists", radiologists.get());
    });

    Effect::new(move |_| {
        let _ = LocalStorage::set("radsched_vacations", vacations.get());
    });

    Effect::new(move |_| {
        let _ = LocalStorage::set("radsched_schedule", schedule.get());
    });

    Effect::new(move |_| {
        let _ = LocalStorage::set("radsched_selected_year", selected_year.get());
        let _ = LocalStorage::set("radsched_selected_month", selected_month.get());
    });

    // Solver Callback Trigger
    let run_auto_solver = move |()| {
        let rads = radiologists.get();
        let svcs = services.get();
        let vacs = vacations.get();
        let holis = holidays.get();

        let solver = ScheduleSolver::new(&rads, &svcs, &vacs, &holis);
        let mut current = schedule.get();

        // Run 6,000 iterations of Simulated Annealing
        solver.solve(&mut current, 6000);
        set_schedule.set(current);
    };

    // Computes header metrics
    let score = move || schedule.get().score;
    let violations = move || schedule.get().hard_violations;

    view! {
        <div class="app-container">
            <Navbar
                active_tab=active_tab
                set_active_tab=set_active_tab
                on_solve=Callback::new(run_auto_solver)
                on_open_email=Callback::new(move |()| set_is_email_open.set(true))
                on_open_sheets=Callback::new(move |()| set_is_sheets_open.set(true))
                score=Signal::derive(score)
                violations=Signal::derive(violations)
            />

            <main class="main-content">
                {move || match active_tab.get() {
                    ActiveTab::ScheduleGrid => view! {
                        <ScheduleGrid
                            schedule=schedule
                            radiologists=radiologists
                            services=services
                            selected_month=selected_month
                            selected_year=selected_year
                            set_selected_month=set_selected_month
                            set_selected_year=set_selected_year
                            on_select_slot=Callback::new(move |slot| set_selected_slot.set(Some(slot)))
                        />
                    }.into_any(),

                    ActiveTab::Ledger => view! {
                        <LedgerManager
                            radiologists=radiologists
                            set_radiologists=set_radiologists
                            schedule=schedule
                            services=services
                        />
                    }.into_any(),

                    ActiveTab::Radiologists => view! {
                        <RadiologistsManager
                            radiologists=radiologists
                            set_radiologists=set_radiologists
                            services=services
                            set_schedule=set_schedule
                        />
                    }.into_any(),

                    ActiveTab::VacationRequests => view! {
                        <VacationManager
                            radiologists=radiologists
                            vacations=vacations
                            set_vacations=set_vacations
                            selected_year=selected_year
                            selected_month=selected_month
                        />
                    }.into_any(),
                }}
            </main>

            <SwapModal
                slot=selected_slot
                on_close=Callback::new(move |()| set_selected_slot.set(None))
                radiologists=radiologists
                services=services
                vacations=vacations
                set_schedule=set_schedule
            />

            <EmailModal
                is_open=is_email_open
                on_close=Callback::new(move |()| set_is_email_open.set(false))
                schedule=schedule
                radiologists=radiologists
                services=services
            />

            <SheetsModal
                is_open=is_sheets_open
                on_close=Callback::new(move |()| set_is_sheets_open.set(false))
                webhook_url=webhook_url
                set_webhook_url=set_webhook_url
            />
        </div>
    }
}
