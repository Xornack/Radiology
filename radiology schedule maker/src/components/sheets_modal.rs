use leptos::prelude::*;

#[component]
pub fn SheetsModal(
    is_open: ReadSignal<bool>,
    on_close: Callback<()>,
    webhook_url: ReadSignal<String>,
    set_webhook_url: WriteSignal<String>,
) -> impl IntoView {
    let script_template = r#"function doPost(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var data = JSON.parse(e.postData.contents);
  
  sheet.clearContents();
  sheet.appendRow(["Date", "Service", "Attending"]);
  
  data.slots.forEach(function(slot) {
    sheet.appendRow([slot.date, slot.service_id, slot.assigned_radiologist_id || "Unassigned"]);
  });
  
  return ContentService.createTextOutput(JSON.stringify({result: "success"}))
    .setMimeType(ContentService.MimeType.JSON);
}"#;

    view! {
        {move || {
            if is_open.get() {
                view! {
                    <div class="modal-backdrop" on:click=move |_| on_close.run(())>
                        <div class="modal-card" style="max-width: 750px;" on:click=move |e| e.stop_propagation()>
                            <div class="modal-header">
                                <div class="modal-title">"📊 Google Sheets Integration Setup"</div>
                                <button class="btn btn-secondary btn-sm" on:click=move |_| on_close.run(())>"✕ Close"</button>
                            </div>

                            <div class="form-group">
                                <label class="form-label">"Google Apps Script Web App Endpoint URL:"</label>
                                <input
                                    type="text"
                                    class="form-input"
                                    placeholder="https://script.google.com/macros/s/.../exec"
                                    prop:value=webhook_url
                                    on:input=move |e| set_webhook_url.set(event_target_value(&e))
                                />
                            </div>

                            <div style="font-size: 0.85rem; font-weight: 600; color: var(--secondary); margin-bottom: 0.5rem;">
                                "Google Apps Script 1-Minute Setup Guide:"
                            </div>
                            <ol style="font-size: 0.8rem; color: var(--text-muted); margin-left: 1.2rem; display: flex; flex-direction: column; gap: 0.4rem;">
                                <li>"Open your department Google Sheet."</li>
                                <li>"Click " <b>"Extensions > Apps Script"</b> "."</li>
                                <li>"Paste the code snippet below and click Save."</li>
                                <li>"Click " <b>"Deploy > New deployment"</b> " -> Select " <b>"Web app"</b> "."</li>
                                <li>"Set Access to " <b>"Anyone"</b> " and copy the Web App URL into the input above."</li>
                            </ol>

                            <div class="code-box" style="margin-top: 1rem;">
                                {script_template}
                            </div>

                            <div style="display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1.25rem;">
                                <button class="btn btn-primary" on:click=move |_| on_close.run(())>
                                    "Save Settings & Close"
                                </button>
                            </div>
                        </div>
                    </div>
                }.into_any()
            } else {
                let _: () = view! {};
                ().into_any()
            }
        }}
    }
}
