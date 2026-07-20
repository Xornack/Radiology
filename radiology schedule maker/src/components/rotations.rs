use crate::models::{Holiday, Service, ServiceCadence};
use leptos::prelude::*;

fn cadence_label(cadence: ServiceCadence) -> &'static str {
    match cadence {
        ServiceCadence::AllDays => "All days",
        ServiceCadence::Weekdays => "Weekdays",
        ServiceCadence::Weekends => "Weekends",
    }
}

#[component]
pub fn RotationsManager(
    services: ReadSignal<Vec<Service>>,
    set_services: WriteSignal<Vec<Service>>,
    holidays: ReadSignal<Vec<Holiday>>,
    set_holidays: WriteSignal<Vec<Holiday>>,
    selected_year: ReadSignal<i32>,
    selected_month: ReadSignal<u32>,
) -> impl IntoView {
    let (new_name, set_new_name) = signal(String::new());
    let (new_cadence, set_new_cadence) = signal(ServiceCadence::Weekdays);
    let (new_required, set_new_required) = signal(true);
    let (new_bundle_with, set_new_bundle_with) = signal(String::new());

    let add_rotation = move |_| {
        let name = new_name.get();
        if name.trim().is_empty() {
            return;
        }

        let id = format!("svc_{}", name.trim().to_lowercase().replace(' ', "_"));
        if services.get().iter().any(|s| s.id == id) {
            return; // a rotation with this name already exists
        }

        let bundled_with = {
            let b = new_bundle_with.get();
            if b.is_empty() { None } else { Some(b) }
        };

        let new_svc = Service {
            id,
            name: name.clone(),
            category: crate::models::ServiceCategory::ShiftCoverage,
            is_weekend: new_cadence.get() == ServiceCadence::Weekends,
            is_night_call: false,
            bundled_with,
            description: String::new(),
            cadence: new_cadence.get(),
            required: new_required.get(),
        };

        set_services.update(|list| list.push(new_svc));
        set_new_name.set(String::new());
        set_new_bundle_with.set(String::new());
    };

    view! {
        <div style="display: grid; grid-template-columns: 1fr 360px; gap: 1.5rem;">
            <div>
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">"🔁 Rotations & Services"</span>
                        <span class="badge badge-primary">{move || format!("{} Rotations", services.get().len())}</span>
                    </div>

                    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                        {move || {
                            services.get().into_iter().map(|svc| {
                                let svc_id = svc.id.clone();
                                view! {
                                    <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 1rem; display: flex; align-items: center; justify-content: space-between; gap: 1rem;">
                                        <div style="display: flex; flex-direction: column; gap: 0.4rem;">
                                            <div style="font-weight: 600;">{svc.name.clone()}</div>
                                            <div style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
                                                <span class="badge badge-primary">{cadence_label(svc.cadence)}</span>
                                                {if svc.required {
                                                    view! { <span class="badge badge-warning">"Required"</span> }.into_any()
                                                } else {
                                                    view! { <span class="badge badge-success">"Optional"</span> }.into_any()
                                                }}
                                                {svc.bundled_with.clone().map(|b| view! {
                                                    <span class="badge badge-primary">{format!("🔗 Co-covers {}", b)}</span>
                                                })}
                                            </div>
                                        </div>
                                        <button
                                            class="btn btn-secondary btn-sm"
                                            on:click=move |_| {
                                                set_services.update(|list| list.retain(|s| s.id != svc_id));
                                            }
                                        >
                                            "Remove"
                                        </button>
                                    </div>
                                }
                            }).collect_view()
                        }}
                    </div>
                </div>

                // Holidays section (filled in by the rotations-cadence-holidays plan, Task 7)
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title">"➕ Add New Rotation"</span>
                </div>

                <div class="form-group">
                    <label class="form-label">"Rotation Name"</label>
                    <input
                        type="text"
                        class="form-input"
                        placeholder="e.g. Weekend Float"
                        prop:value=new_name
                        on:input=move |e| set_new_name.set(event_target_value(&e))
                    />
                </div>

                <div class="form-group">
                    <label class="form-label">"Cadence"</label>
                    <select
                        class="form-select"
                        on:change=move |e| {
                            let cadence = match event_target_value(&e).as_str() {
                                "weekends" => ServiceCadence::Weekends,
                                "all_days" => ServiceCadence::AllDays,
                                _ => ServiceCadence::Weekdays,
                            };
                            set_new_cadence.set(cadence);
                        }
                    >
                        <option value="weekdays">"Weekdays"</option>
                        <option value="weekends">"Weekends"</option>
                        <option value="all_days">"All days"</option>
                    </select>
                </div>

                <div class="form-group">
                    <label class="form-label">"Bundles With (optional)"</label>
                    <select
                        class="form-select"
                        on:change=move |e| set_new_bundle_with.set(event_target_value(&e))
                    >
                        <option value="">"-- None --"</option>
                        {move || {
                            services.get().into_iter().map(|s| {
                                view! { <option value={s.id.clone()}>{s.name.clone()}</option> }
                            }).collect_view()
                        }}
                    </select>
                </div>

                <div class="form-group">
                    <label class="checkbox-item" style="margin-top: 0.5rem;">
                        <input
                            type="checkbox"
                            prop:checked=new_required
                            on:change=move |e| set_new_required.set(event_target_checked(&e))
                        />
                        <span>"Required (unfilled slots count against the score)"</span>
                    </label>
                </div>

                <button class="btn btn-primary" style="width: 100%; margin-top: 1rem;" on:click=add_rotation>
                    "Add Rotation"
                </button>
            </div>
        </div>
    }
}
