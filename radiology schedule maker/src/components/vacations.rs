use crate::models::{Radiologist, VacationRequest};
use leptos::prelude::*;
use std::collections::HashMap;

#[component]
pub fn VacationManager(
    radiologists: ReadSignal<Vec<Radiologist>>,
    vacations: ReadSignal<Vec<VacationRequest>>,
    set_vacations: WriteSignal<Vec<VacationRequest>>,
    selected_year: ReadSignal<i32>,
    selected_month: ReadSignal<u32>,
) -> impl IntoView {
    let (selected_rad_id, set_selected_rad_id) = signal(String::new());
    let (selected_day, set_selected_day) = signal(1u32);
    let (note, set_note) = signal(String::new());

    let add_vacation = move |_| {
        let rad_id = selected_rad_id.get();
        if rad_id.is_empty() {
            return;
        }

        let date = format!("{:04}-{:02}-{:02}", selected_year.get(), selected_month.get(), selected_day.get());
        let new_id = format!("v_{}_{}", rad_id, selected_day.get());

        let new_req = VacationRequest::new(new_id, rad_id, date, note.get());
        set_vacations.update(|list| list.push(new_req));
        set_note.set(String::new());
    };

    view! {
        <div style="display: grid; grid-template-columns: 1fr 340px; gap: 1.5rem;">
            <div class="card">
                <div class="card-header">
                    <span class="card-title">"🏖️ Approved Attending Vacation & PTO Blackouts"</span>
                    <span class="badge badge-warning">{move || format!("{} Requests", vacations.get().len())}</span>
                </div>

                <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                    {move || {
                        let vacs = vacations.get();
                        let rads = radiologists.get();
                        let rad_map: HashMap<String, String> = rads.into_iter().map(|r| (r.id, r.name)).collect();

                        if vacs.is_empty() {
                            view! { <div style="color: var(--text-dim); font-style: italic;">"No vacation requests entered for this month."</div> }.into_any()
                        } else {
                            vacs.into_iter().map(|vac| {
                                let vac_id = vac.id.clone();
                                let rad_name = rad_map.get(&vac.radiologist_id)
                                    .cloned()
                                    .unwrap_or_else(|| "Unknown Attending".to_string());

                                view! {
                                    <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 0.75rem 1rem; display: flex; align-items: center; justify-content: space-between;">
                                        <div>
                                            <div style="font-weight: 600; color: #fcd34d;">{rad_name}</div>
                                            <div style="font-size: 0.8rem; color: var(--text-muted);">
                                                "📅 Date: " <span style="font-family: var(--font-mono); color: var(--secondary);">{vac.date}</span>
                                                {if !vac.note.is_empty() { format!(" — Note: {}", vac.note) } else { "".into() }}
                                            </div>
                                        </div>

                                        <button
                                            class="btn btn-secondary btn-sm"
                                            on:click=move |_| {
                                                set_vacations.update(|list| list.retain(|v| v.id != vac_id));
                                            }
                                        >
                                            "Delete"
                                        </button>
                                    </div>
                                }
                            }).collect_view().into_any()
                        }
                    }}
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title">"➕ Add Vacation / PTO Blockout"</span>
                </div>

                <div class="form-group">
                    <label class="form-label">"Select Attending"</label>
                    <select
                        class="form-select"
                        on:change=move |e| set_selected_rad_id.set(event_target_value(&e))
                    >
                        <option value="">"-- Select Attending --"</option>
                        {move || {
                            radiologists.get().into_iter().map(|r| {
                                view! { <option value={r.id.clone()}>{r.name}</option> }
                            }).collect_view()
                        }}
                    </select>
                </div>

                <div class="form-group">
                    <label class="form-label">"Day of Month (1 - 31)"</label>
                    <input
                        type="number"
                        class="form-input"
                        min="1"
                        max="31"
                        prop:value=move || selected_day.get().to_string()
                        on:input=move |e| {
                            if let Ok(val) = event_target_value(&e).parse::<u32>() {
                                set_selected_day.set(val);
                            }
                        }
                    />
                </div>

                <div class="form-group">
                    <label class="form-label">"Note / Reason (Optional)"</label>
                    <input
                        type="text"
                        class="form-input"
                        placeholder="e.g. Annual Conference / PTO"
                        prop:value=note
                        on:input=move |e| set_note.set(event_target_value(&e))
                    />
                </div>

                <button class="btn btn-primary" style="width: 100%; margin-top: 1rem;" on:click=add_vacation>
                    "Record Vacation Blockout"
                </button>
            </div>
        </div>
    }
}
