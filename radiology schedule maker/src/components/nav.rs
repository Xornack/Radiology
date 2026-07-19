use leptos::prelude::*;

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum ActiveTab {
    ScheduleGrid,
    Radiologists,
    VacationRequests,
    Ledger,
}

#[component]
pub fn Navbar(
    active_tab: ReadSignal<ActiveTab>,
    set_active_tab: WriteSignal<ActiveTab>,
    on_solve: Callback<()>,
    on_open_email: Callback<()>,
    on_open_sheets: Callback<()>,
    score: Signal<f64>,
    violations: Signal<u32>,
) -> impl IntoView {
    view! {
        <nav class="navbar">
            <div class="brand">
                <div class="brand-logo">"R"</div>
                <div>
                    <span class="brand-title">"RadSched"</span>
                    <span class="brand-badge" style="margin-left: 0.5rem;">"WASM Solver"</span>
                </div>
            </div>

            <div class="nav-tabs">
                <button
                    class=move || if active_tab.get() == ActiveTab::ScheduleGrid { "nav-tab active" } else { "nav-tab" }
                    on:click=move |_| set_active_tab.set(ActiveTab::ScheduleGrid)
                >
                    "📅 Schedule Grid"
                </button>
                <button
                    class=move || if active_tab.get() == ActiveTab::Ledger { "nav-tab active" } else { "nav-tab" }
                    on:click=move |_| set_active_tab.set(ActiveTab::Ledger)
                >
                    "⚖️ Tallies & Owed Days"
                </button>
                <button
                    class=move || if active_tab.get() == ActiveTab::Radiologists { "nav-tab active" } else { "nav-tab" }
                    on:click=move |_| set_active_tab.set(ActiveTab::Radiologists)
                >
                    "👨‍⚕️ Radiologists Roster"
                </button>
                <button
                    class=move || if active_tab.get() == ActiveTab::VacationRequests { "nav-tab active" } else { "nav-tab" }
                    on:click=move |_| set_active_tab.set(ActiveTab::VacationRequests)
                >
                    "🏖️ Vacation / PTO"
                </button>
            </div>

            <div class="nav-actions">
                <div class="solver-stat">
                    <div class="stat-item">
                        <span class="stat-label">"Penalty Score"</span>
                        <span class="stat-value">{move || format!("{:.1}", score.get())}</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">"Conflicts"</span>
                        <span class="stat-value" style={move || if violations.get() > 0 { "color: var(--danger);" } else { "color: var(--success);" }}>
                            {move || violations.get()}
                        </span>
                    </div>
                </div>

                <button class="btn btn-primary" on:click=move |_| on_solve.run(())>
                    "⚡ Auto-Generate Schedule"
                </button>
                <button class="btn btn-secondary btn-sm" on:click=move |_| on_open_email.run(())>
                    "✉️ Export Email"
                </button>
                <button class="btn btn-secondary btn-sm" on:click=move |_| on_open_sheets.run(())>
                    "📊 Google Sheets Sync"
                </button>
            </div>
        </nav>
    }
}
