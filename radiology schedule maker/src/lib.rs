pub mod app;
pub mod components;
pub mod models;
pub mod solver;
pub mod utils;

use app::App;
use wasm_bindgen::prelude::*;

#[wasm_bindgen(start)]
pub fn run_app() {
    console_error_panic_hook::set_once();
    leptos::mount::mount_to_body(App);
}
