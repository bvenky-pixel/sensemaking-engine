import { mount } from 'svelte'
import './lib/tokens.css'
import { applyReduceMotionAttribute } from './lib/motionPreference.js'
import App from './App.svelte'

// Settings' "Reduce motion" toggle (see frontend/decisions.md "Reduce
// motion, as a real setting"): applied once here at startup so the
// preference is already in effect on first paint, not just after
// visiting Settings.
applyReduceMotionAttribute()

const app = mount(App, {
  target: document.getElementById('app'),
})

export default app
