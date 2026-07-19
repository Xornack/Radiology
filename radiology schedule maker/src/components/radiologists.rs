use crate::models::{derive_initials, Radiologist, Service};
use leptos::prelude::*;
use std::collections::HashSet;

#[component]
pub fn RadiologistsManager(
    radiologists: ReadSignal<Vec<Radiologist>>,
    set_radiologists: WriteSignal<Vec<Radiologist>>,
    services: ReadSignal<Vec<Service>>,
) -> impl IntoView {
    let (new_name, set_new_name) = signal(String::new());
    let (new_initials, set_new_initials) = signal(String::new());
    let (can_call, set_can_call) = signal(true);
    let (target_shifts, set_target_shifts) = signal(16u32);

    let add_radiologist = move |_| {
        let name = new_name.get();
        if name.trim().is_empty() {
            return;
        }

        let initials = if new_initials.get().trim().is_empty() {
            derive_initials(&name)
        } else {
            new_initials.get().trim().to_uppercase()
        };

        let new_id = format!("rad_{}", radiologists.get().len() + 1);
        let mut allowed: HashSet<String> = HashSet::new();
        allowed.insert("ALL".to_string()); // Default generalist

        let new_rad = Radiologist {
            id: new_id,
            name,
            initials,
            allowed_services: allowed,
            can_cover_call: can_call.get(),
            target_monthly_shifts: target_shifts.get(),
            color_code: "#6366f1".to_string(),
            owed_days_notes: String::new(),
        };

        set_radiologists.update(|list| list.push(new_rad));
        set_new_name.set(String::new());
        set_new_initials.set(String::new());
    };

    view! {
        <div style="display: grid; grid-template-columns: 1fr 340px; gap: 1.5rem;">
            <div class="card">
                <div class="card-header">
                    <span class="card-title">"👨‍⚕️ Attending Radiologists Roster & Initials"</span>
                    <span class="badge badge-primary">{move || format!("{} Attendings", radiologists.get().len())}</span>
                </div>

                <div style="display: flex; flex-direction: column; gap: 1rem;">
                    {move || {
                        let rads = radiologists.get();
                        let svcs = services.get();

                        rads.into_iter().map(|rad| {
                            let rad_id = rad.id.clone();
                            let is_generalist = rad.allowed_services.contains("ALL");

                            view! {
                                <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 1rem; display: flex; align-items: center; justify-content: space-between; gap: 1rem;">
                                    <div style="display: flex; flex-direction: column; gap: 0.25rem;">
                                        <div style="font-weight: 600; font-size: 1rem; display: flex; align-items: center; gap: 0.5rem;">
                                            <span class="rad-pill" style="width: auto; padding: 0.2rem 0.6rem;">{rad.display_badge()}</span>
                                            <span>{rad.name.clone()}</span>
                                            {if rad.can_cover_call {
                                                view! { <span class="badge badge-success">"🌙 Call Eligible"</span> }.into_any()
                                            } else {
                                                view! { <span class="badge badge-warning">"Daytime Only"</span> }.into_any()
                                            }}
                                        </div>

                                        <div style="display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.4rem;">
                                            {if is_generalist {
                                                view! { <span class="badge badge-primary">"🌟 Generalist (Covers All Services)"</span> }.into_any()
                                            } else {
                                                rad.allowed_services.iter().map(|s_id| {
                                                    let s_name = svcs.iter().find(|s| &s.id == s_id).map(|s| s.name.as_str()).unwrap_or(s_id);
                                                    view! { <span class="badge badge-primary">{s_name.to_string()}</span> }
                                                }).collect_view().into_any()
                                            }}
                                        </div>
                                    </div>

                                    <div style="display: flex; align-items: center; gap: 1rem;">
                                        <div style="text-align: right;">
                                            <div style="font-size: 0.75rem; color: var(--text-dim);">"Target"</div>
                                            <div style="font-family: var(--font-mono); font-weight: 600; font-size: 1.1rem; color: var(--secondary);">
                                                {format!("{} shifts", rad.target_monthly_shifts)}
                                            </div>
                                        </div>

                                        <button
                                            class="btn btn-secondary btn-sm"
                                            on:click=move |_| {
                                                set_radiologists.update(|list| list.retain(|r| r.id != rad_id));
                                            }
                                        >
                                            "Remove"
                                        </button>
                                    </div>
                                </div>
                            }
                        }).collect_view()
                    }}
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title">"➕ Add New Attending"</span>
                </div>

                <div class="form-group">
                    <label class="form-label">"Full Name"</label>
                    <input
                        type="text"
                        class="form-input"
                        placeholder="e.g. Dr. Sean Boone"
                        prop:value=new_name
                        on:input=move |e| set_new_name.set(event_target_value(&e))
                    />
                </div>

                <div class="form-group">
                    <label class="form-label">"Schedule Initials / Abbreviation"</label>
                    <input
                        type="text"
                        class="form-input"
                        placeholder="e.g. SBO or MH"
                        prop:value=new_initials
                        on:input=move |e| set_new_initials.set(event_target_value(&e))
                    />
                </div>

                <div class="form-group">
                    <label class="form-label">"Target Monthly Shifts"</label>
                    <input
                        type="number"
                        class="form-input"
                        min="1"
                        max="30"
                        prop:value=move || target_shifts.get().to_string()
                        on:input=move |e| {
                            if let Ok(val) = event_target_value(&e).parse::<u32>() {
                                set_target_shifts.set(val);
                            }
                        }
                    />
                </div>

                <div class="form-group">
                    <label class="checkbox-item" style="margin-top: 0.5rem;">
                        <input
                            type="checkbox"
                            prop:checked=can_call
                            on:change=move |e| set_can_call.set(event_target_checked(&e))
                        />
                        <span>"Eligible for Call Duties"</span>
                    </label>
                </div>

                <button class="btn btn-primary" style="width: 100%; margin-top: 1rem;" on:click=add_radiologist>
                    "Add Attending to Roster"
                </button>
            </div>
        </div>
    }
}
