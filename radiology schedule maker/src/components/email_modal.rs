use crate::models::{MonthlySchedule, Radiologist, Service};
use leptos::prelude::*;
use std::collections::HashMap;

#[component]
pub fn EmailModal(
    is_open: ReadSignal<bool>,
    on_close: Callback<()>,
    schedule: ReadSignal<MonthlySchedule>,
    radiologists: ReadSignal<Vec<Radiologist>>,
    services: ReadSignal<Vec<Service>>,
) -> impl IntoView {
    let copy_to_clipboard = move |text: String| {
        if let Some(window) = web_sys::window() {
            let navigator = window.navigator();
            let clipboard = navigator.clipboard();
            let _ = clipboard.write_text(&text);
        }
    };

    let generate_email_text = move || {
        let sched = schedule.get();
        let rads = radiologists.get();
        let svcs = services.get();

        let rad_map: HashMap<String, String> = rads.into_iter().map(|r| (r.id, r.name)).collect();
        let svc_map: HashMap<String, String> = svcs.into_iter().map(|s| (s.id, s.name)).collect();

        let mut output = String::new();
        output.push_str(&format!("Subject: Radiology Attending Coverage Schedule — Month {}/{}\n\n", sched.month, sched.year));
        output.push_str("Dear Attendings,\n\nHere is the published radiology coverage schedule for the upcoming month:\n\n");

        let mut current_day = 0;
        for slot in sched.slots {
            if slot.day_number != current_day {
                current_day = slot.day_number;
                output.push_str(&format!("\n📅 --- Day {} ({}) ---\n", current_day, slot.date));
            }

            let svc_name = svc_map.get(&slot.service_id).cloned().unwrap_or(slot.service_id);
            let rad_name = slot.assigned_radiologist_id.as_ref()
                .and_then(|id| rad_map.get(id))
                .cloned()
                .unwrap_or_else(|| "UNASSIGNED".to_string());

            output.push_str(&format!("  - {}: {}\n", svc_name, rad_name));
        }

        output.push_str("\n\nPlease review your assigned shifts. For shift swaps, contact the scheduling chief.\nBest regards,\nRadiology Scheduling Team");
        output
    };

    view! {
        {move || {
            if is_open.get() {
                let text = generate_email_text();
                let text_copy = text.clone();

                view! {
                    <div class="modal-backdrop" on:click=move |_| on_close.run(())>
                        <div class="modal-card" style="max-width: 750px;" on:click=move |e| e.stop_propagation()>
                            <div class="modal-header">
                                <div class="modal-title">"✉️ Published Schedule Email & Communication Exporter"</div>
                                <button class="btn btn-secondary btn-sm" on:click=move |_| on_close.run(())>"✕ Close"</button>
                            </div>

                            <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem;">
                                "Copy the formatted text below to send via departmental listserv email:"
                            </div>

                            <div class="code-box">
                                {text.clone()}
                            </div>

                            <div style="display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1.25rem;">
                                <button class="btn btn-secondary" on:click=move |_| on_close.run(())>"Close"</button>
                                <button
                                    class="btn btn-primary"
                                    on:click=move |_| copy_to_clipboard(text_copy.clone())
                                >
                                    "📋 Copy Email Text to Clipboard"
                                </button>
                            </div>
                        </div>
                    </div>
                }.into_any()
            } else {
                view! {}.into_any()
            }
        }}
    }
}
