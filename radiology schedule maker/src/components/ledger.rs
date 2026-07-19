use crate::models::{MonthlySchedule, Radiologist, Service};
use leptos::prelude::*;
use std::collections::HashMap;

#[component]
pub fn LedgerManager(
    radiologists: ReadSignal<Vec<Radiologist>>,
    set_radiologists: WriteSignal<Vec<Radiologist>>,
    schedule: ReadSignal<MonthlySchedule>,
    services: ReadSignal<Vec<Service>>,
) -> impl IntoView {
    let (selected_rad_id, set_selected_rad_id) = signal(String::new());
    let (edit_note, set_edit_note) = signal(String::new());

    let update_owed_days = move |_| {
        let rad_id = selected_rad_id.get();
        if rad_id.is_empty() {
            return;
        }

        let note = edit_note.get();
        set_radiologists.update(|list| {
            if let Some(r) = list.iter_mut().find(|r| r.id == rad_id) {
                r.owed_days_notes = note;
            }
        });
        set_edit_note.set(String::new());
    };

    // Compute shift tallies per attending
    let shift_tallies = move || {
        let sched = schedule.get();
        let svcs = services.get();
        let svc_map: HashMap<String, Service> = svcs.into_iter().map(|s| (s.id.clone(), s)).collect();

        struct Tally {
            total_shifts: u32,
            call_shifts: u32,
            dates_worked: Vec<u32>,
        }

        let mut map: HashMap<String, Tally> = HashMap::new();

        for slot in sched.slots {
            if let Some(ref rad_id) = slot.assigned_radiologist_id {
                let entry = map.entry(rad_id.clone()).or_insert_with(|| Tally {
                    total_shifts: 0,
                    call_shifts: 0,
                    dates_worked: Vec::new(),
                });

                entry.total_shifts += 1;
                if !entry.dates_worked.contains(&slot.day_number) {
                    entry.dates_worked.push(slot.day_number);
                }

                if let Some(svc) = svc_map.get(&slot.service_id) {
                    if svc.is_weekend || svc.is_night_call {
                        entry.call_shifts += 1;
                    }
                }
            }
        }

        for t in map.values_mut() {
            t.dates_worked.sort();
        }

        map
    };

    view! {
        <div style="display: grid; grid-template-columns: 1fr 380px; gap: 1.5rem;">
            <div class="card">
                <div class="card-header">
                    <span class="card-title">"📊 Shift Tallies & Cross Coverage Tracker ('Who Has Done What')"</span>
                </div>

                <div class="grid-container" style="max-height: 500px; overflow-y: auto;">
                    <table class="schedule-table" style="width: 100%;">
                        <thead>
                            <tr>
                                <th style="text-align: left; padding-left: 1rem;">"Attending"</th>
                                <th>"Initials"</th>
                                <th>"Total Shifts"</th>
                                <th>"Call Shifts"</th>
                                <th style="text-align: left;">"Dates Worked (Block)"</th>
                            </tr>
                        </thead>
                        <tbody>
                            {move || {
                                let rads = radiologists.get();
                                let tallies = shift_tallies();

                                rads.into_iter().map(|rad| {
                                    let rad_id = rad.id.clone();
                                    let tally = tallies.get(&rad_id);
                                    let total = tally.map(|t| t.total_shifts).unwrap_or(0);
                                    let call = tally.map(|t| t.call_shifts).unwrap_or(0);
                                    let dates_str = tally
                                        .map(|t| t.dates_worked.iter().map(|d| d.to_string()).collect::<Vec<String>>().join(", "))
                                        .unwrap_or_else(|| "None".to_string());

                                    view! {
                                        <tr>
                                            <td style="text-align: left; padding-left: 1rem; font-weight: 600;">{rad.name.clone()}</td>
                                            <td>
                                                <span class="rad-pill" style="width: auto; padding: 0.2rem 0.6rem;">{rad.display_badge()}</span>
                                            </td>
                                            <td style="font-family: var(--font-mono); font-weight: 600; color: var(--secondary);">{total}</td>
                                            <td style="font-family: var(--font-mono); font-weight: 600; color: var(--warning);">{call}</td>
                                            <td style="text-align: left; font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-muted);">{dates_str}</td>
                                        </tr>
                                    }
                                }).collect_view()
                            }}
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title">"⚖️ Owed Days & Compensatory Credit ('Who Is Owed What')"</span>
                </div>

                <div style="display: flex; flex-direction: column; gap: 0.75rem; margin-bottom: 1.5rem; max-height: 320px; overflow-y: auto;">
                    {move || {
                        let rads = radiologists.get();
                        rads.into_iter().map(|rad| {
                            let note = if rad.owed_days_notes.is_empty() { "No owed days recorded" } else { &rad.owed_days_notes };
                            let has_notes = !rad.owed_days_notes.is_empty();

                            view! {
                                <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 0.75rem; display: flex; align-items: center; justify-content: space-between;">
                                    <div>
                                        <div style="font-weight: 600; color: #a5b4fc; font-size: 0.9rem;">
                                            {rad.name.clone()} <span style="font-size: 0.75rem; color: var(--text-dim);">({rad.display_badge()})</span>
                                        </div>
                                        <div style=format!("font-size: 0.8rem; {};", if has_notes { "color: #fcd34d; font-weight: 500;" } else { "color: var(--text-dim);" })>
                                            {note.to_string()}
                                        </div>
                                    </div>
                                </div>
                            }
                        }).collect_view()
                    }}
                </div>

                <div style="border-top: 1px solid var(--border-color); padding-top: 1rem;">
                    <div class="form-label">"Update Owed Days Note"</div>
                    <div class="form-group">
                        <select
                            class="form-select"
                            on:change=move |e| set_selected_rad_id.set(event_target_value(&e))
                        >
                            <option value="">"-- Select Attending --"</option>
                            {move || {
                                radiologists.get().into_iter().map(|r| {
                                    view! { <option value={r.id.clone()}>{r.name.clone()} " (" {r.display_badge()} ")" </option> }
                                }).collect_view()
                            }}
                        </select>
                    </div>

                    <div class="form-group">
                        <input
                            type="text"
                            class="form-input"
                            placeholder="e.g. +2 Days for Aug 3rd Call and May 7th Day"
                            prop:value=edit_note
                            on:input=move |e| set_edit_note.set(event_target_value(&e))
                        />
                    </div>

                    <button class="btn btn-primary" style="width: 100%;" on:click=update_owed_days>
                        "Save Owed Days Record"
                    </button>
                </div>
            </div>
        </div>
    }
}
