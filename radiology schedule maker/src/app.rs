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
        LocalStorage::get("radsched_radiologists").unwrap_or_else(|_| default_radiologists())
    );

    let (services, _set_services) = signal(
        LocalStorage::get("radsched_services").unwrap_or_else(|_| default_services())
    );

    let (vacations, set_vacations) = signal(
        LocalStorage::get("radsched_vacations").unwrap_or_else(|_| vec![])
    );

    let (selected_year, set_selected_year) = signal(2026i32);
    let (selected_month, set_selected_month) = signal(7u32); // July 2026

    let (schedule, set_schedule) = signal(MonthlySchedule::new(selected_year.get(), selected_month.get()));

    let (active_tab, set_active_tab) = signal(ActiveTab::ScheduleGrid);
    let (selected_slot, set_selected_slot) = signal(None::<ScheduleSlot>);
    let (is_email_open, set_is_email_open) = signal(false);
    let (is_sheets_open, set_is_sheets_open) = signal(false);
    let (webhook_url, set_webhook_url) = signal(String::new());

    // 2. Initialize schedule slots when month changes or on start
    let initialize_schedule = move || {
        let rads = radiologists.get();
        let svcs = services.get();
        let vacs = vacations.get();

        let total_days = days_in_month(selected_year.get(), selected_month.get());
        let solver = ScheduleSolver::new(&rads, &svcs, &vacs);
        let mut new_sched = solver.create_empty_schedule(selected_year.get(), selected_month.get(), total_days);
        solver.initialize_greedy(&mut new_sched);
        set_schedule.set(new_sched);
    };

    Effect::new(move |_| {
        initialize_schedule();
    });

    // LocalStorage persistence effects
    Effect::new(move |_| {
        let _ = LocalStorage::set("radsched_radiologists", &radiologists.get());
    });

    Effect::new(move |_| {
        let _ = LocalStorage::set("radsched_vacations", &vacations.get());
    });

    // Solver Callback Trigger
    let run_auto_solver = move |()| {
        let rads = radiologists.get();
        let svcs = services.get();
        let vacs = vacations.get();

        let solver = ScheduleSolver::new(&rads, &svcs, &vacs);
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
