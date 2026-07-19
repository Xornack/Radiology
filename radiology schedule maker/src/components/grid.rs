use crate::models::{MonthlySchedule, Radiologist, ScheduleSlot, Service};
use crate::utils::calendar::{days_in_month, is_weekend_date, week_day_range, weekday_short_name};
use leptos::prelude::*;
use std::collections::HashMap;

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum ViewMode {
    Monthly,
    Weekly,
}

#[component]
pub fn ScheduleGrid(
    schedule: ReadSignal<MonthlySchedule>,
    radiologists: ReadSignal<Vec<Radiologist>>,
    services: ReadSignal<Vec<Service>>,
    selected_month: ReadSignal<u32>,
    selected_year: ReadSignal<i32>,
    set_selected_month: WriteSignal<u32>,
    set_selected_year: WriteSignal<i32>,
    on_select_slot: Callback<ScheduleSlot>,
) -> impl IntoView {
    let (view_mode, set_view_mode) = signal(ViewMode::Monthly);
    let (selected_week, set_selected_week) = signal(1u32); // Week 1 to 5

    let year = move || selected_year.get();
    let month = move || selected_month.get();
    let total_days = move || days_in_month(year(), month());

    // Create lookup maps for fast rendering
    let rad_map = move || {
        let rads = radiologists.get();
        let map: HashMap<String, Radiologist> = rads.into_iter().map(|r| (r.id.clone(), r)).collect();
        map
    };

    let slots_by_service_day = move || {
        let sched = schedule.get();
        let mut map: HashMap<(String, u32), ScheduleSlot> = HashMap::new();
        for slot in sched.slots {
            map.insert((slot.service_id.clone(), slot.day_number), slot);
        }
        map
    };

    let slots_by_day = move || {
        let sched = schedule.get();
        let mut map: HashMap<u32, Vec<ScheduleSlot>> = HashMap::new();
        for slot in sched.slots {
            map.entry(slot.day_number).or_default().push(slot);
        }
        map
    };

    // Computes start & end day for selected week
    let week_days = move || {
        let max_days = total_days();
        week_day_range(selected_week.get(), max_days)
            .map(|(start, end)| (start..=end).collect::<Vec<u32>>())
            .unwrap_or_default()
    };

    let prev_month = move |_| {
        let cur_m = selected_month.get();
        if cur_m == 1 {
            set_selected_month.set(12);
            set_selected_year.set(selected_year.get() - 1);
        } else {
            set_selected_month.set(cur_m - 1);
        }
    };

    let next_month = move |_| {
        let cur_m = selected_month.get();
        if cur_m == 12 {
            set_selected_month.set(1);
            set_selected_year.set(selected_year.get() + 1);
        } else {
            set_selected_month.set(cur_m + 1);
        }
    };

    view! {
        <div>
            <div class="toolbar">
                <div class="month-picker">
                    <button class="btn btn-secondary btn-sm" on:click=prev_month>"◀ Previous Month"</button>
                    <span class="month-title">
                        {move || match selected_month.get() {
                            1 => "January",
                            2 => "February",
                            3 => "March",
                            4 => "April",
                            5 => "May",
                            6 => "June",
                            7 => "July",
                            8 => "August",
                            9 => "September",
                            10 => "October",
                            11 => "November",
                            _ => "December",
                        }} " " {move || selected_year.get()}
                    </span>
                    <button class="btn btn-secondary btn-sm" on:click=next_month>"Next Month ▶"</button>
                </div>

                <div class="toggle-group">
                    <button
                        class=move || if view_mode.get() == ViewMode::Monthly { "toggle-btn active" } else { "toggle-btn" }
                        on:click=move |_| set_view_mode.set(ViewMode::Monthly)
                    >
                        "📊 Monthly View (Full Grid)"
                    </button>
                    <button
                        class=move || if view_mode.get() == ViewMode::Weekly { "toggle-btn active" } else { "toggle-btn" }
                        on:click=move |_| set_view_mode.set(ViewMode::Weekly)
                    >
                        "📆 Weekly View (Detailed)"
                    </button>
                </div>

                {move || {
                    if view_mode.get() == ViewMode::Weekly {
                        view! {
                            <div class="toggle-group">
                                { (1..=5).filter(|w| week_day_range(*w, total_days()).is_some()).map(|w| {
                                    let is_active = selected_week.get() == w;
                                    view! {
                                        <button
                                            class=if is_active { "toggle-btn active" } else { "toggle-btn" }
                                            on:click=move |_| set_selected_week.set(w)
                                        >
                                            {format!("Week {}", w)}
                                        </button>
                                    }
                                }).collect_view() }
                            </div>
                        }.into_any()
                    } else {
                        view! {}.into_any()
                    }
                }}
            </div>

            {move || match view_mode.get() {
                ViewMode::Monthly => view! {
                    <div class="grid-container">
                        <table class="schedule-table">
                            <thead>
                                <tr>
                                    <th class="service-col">"Daily Service / Call"</th>
                                    { (1..=total_days()).map(|day| {
                                        let y = year();
                                        let m = month();
                                        let day_name = weekday_short_name(y, m, day);
                                        let is_weekend = is_weekend_date(y, m, day);

                                        view! {
                                            <th class=if is_weekend { "weekend-header" } else { "" }>
                                                <div style="font-size: 0.7rem; text-transform: uppercase; color: var(--text-dim);">{day_name}</div>
                                                <div>{format!("{}", day)}</div>
                                            </th>
                                        }
                                    }).collect_view() }
                                </tr>
                            </thead>
                            <tbody>
                                { move || {
                                    let svcs = services.get();
                                    let slots_map = slots_by_service_day();
                                    let rmap = rad_map();
                                    let y = year();
                                    let m = month();
                                    let max_d = total_days();

                                    svcs.into_iter().map(|svc| {
                                        let service_id = svc.id.clone();
                                        let service_name = svc.name.clone();

                                        view! {
                                            <tr>
                                                <td class="service-name">
                                                    <div style="font-weight: 600;">{service_name}</div>
                                                    {if let Some(ref b) = svc.bundled_with {
                                                        view! { <span style="font-size: 0.7rem; color: var(--secondary);">"🔗 Co-covers " {b.clone()}</span> }.into_any()
                                                    } else {
                                                        view! {}.into_any()
                                                    }}
                                                </td>
                                                { (1..=max_d).map(|day| {
                                                    let slot_opt = slots_map.get(&(service_id.clone(), day)).cloned();
                                                    let is_weekend = is_weekend_date(y, m, day);

                                                    if let Some(slot) = slot_opt {
                                                        let slot_clone = slot.clone();
                                                        let rad_short_name = slot.assigned_radiologist_id.as_ref()
                                                            .and_then(|id| rmap.get(id))
                                                            .map(|r| r.display_badge())
                                                            .unwrap_or_else(|| "Unassigned".to_string());

                                                        let is_assigned = slot.assigned_radiologist_id.is_some();
                                                        let is_locked = slot.is_locked;
                                                        let pto_conflict = slot.has_pto_conflict;

                                                        let mut classes = vec!["slot-cell"];
                                                        if is_weekend { classes.push("weekend-cell"); }
                                                        if is_assigned { classes.push("slot-assigned"); }
                                                        if is_locked { classes.push("slot-locked"); }
                                                        if pto_conflict { classes.push("slot-pto-conflict"); }

                                                        view! {
                                                            <td
                                                                class=classes.join(" ")
                                                                on:click=move |_| on_select_slot.run(slot_clone.clone())
                                                            >
                                                                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center;">
                                                                    {if is_assigned {
                                                                        view! {
                                                                            <span class="rad-pill">
                                                                                {if is_locked { "🔒 " } else { "" }}
                                                                                {rad_short_name}
                                                                            </span>
                                                                        }.into_any()
                                                                    } else {
                                                                        view! { <span class="slot-unassigned">"—"</span> }.into_any()
                                                                    }}
                                                                </div>
                                                            </td>
                                                        }.into_any()
                                                    } else {
                                                        view! { <td class="slot-cell">"—"</td> }.into_any()
                                                    }
                                                }).collect_view() }
                                            </tr>
                                        }
                                    }).collect_view()
                                }}
                            </tbody>
                        </table>
                    </div>
                }.into_any(),

                ViewMode::Weekly => view! {
                    <div class="weekly-container">
                        { move || {
                            let days = week_days();
                            let s_by_day = slots_by_day();
                            let svcs = services.get();
                            let rmap = rad_map();
                            let y = year();
                            let m = month();

                            let svc_name_map: HashMap<String, String> = svcs.into_iter().map(|s| (s.id, s.name)).collect();

                            days.into_iter().map(|day| {
                                let day_name = weekday_short_name(y, m, day);
                                let is_weekend = is_weekend_date(y, m, day);
                                let day_slots = s_by_day.get(&day).cloned().unwrap_or_default();

                                view! {
                                    <div class="weekly-day-column">
                                        <div class=if is_weekend { "weekly-day-header weekend" } else { "weekly-day-header" }>
                                            <span>{format!("{} {}", day_name, day)}</span>
                                            <span style="font-size: 0.75rem; font-weight: 500;">
                                                {if is_weekend { "Weekend" } else { "Weekday" }}
                                            </span>
                                        </div>

                                        <div class="weekly-slots-list">
                                            { day_slots.into_iter().map(|slot| {
                                                let slot_clone = slot.clone();
                                                let service_name = svc_name_map.get(&slot.service_id).cloned().unwrap_or(slot.service_id);
                                                let rad_full_name = slot.assigned_radiologist_id.as_ref()
                                                    .and_then(|id| rmap.get(id))
                                                    .map(|r| r.name.clone())
                                                    .unwrap_or_else(|| "Unassigned".to_string());

                                                let is_assigned = slot.assigned_radiologist_id.is_some();

                                                view! {
                                                    <div
                                                        class="weekly-slot-card"
                                                        style=move || {
                                                            let mut bg = "background: rgba(15, 23, 42, 0.6);";
                                                            if !is_assigned { bg = "background: rgba(15, 23, 42, 0.2); border-style: dashed;"; }
                                                            if slot.is_locked { bg = "background: rgba(245, 158, 11, 0.15); border-color: var(--warning);"; }
                                                            if slot.has_pto_conflict { bg = "background: rgba(239, 68, 68, 0.15); border-color: var(--danger);"; }
                                                            bg
                                                        }
                                                        on:click=move |_| on_select_slot.run(slot_clone.clone())
                                                    >
                                                        <div class="weekly-service-title">{service_name}</div>
                                                        <div class="weekly-attending-name">
                                                            {if slot.is_locked { "🔒 " } else { "" }}
                                                            {rad_full_name}
                                                        </div>
                                                    </div>
                                                }
                                            }).collect_view() }
                                        </div>
                                    </div>
                                }
                            }).collect_view()
                        }}
                    </div>
                }.into_any(),
            }}
        </div>
    }
}
