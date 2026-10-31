import '@testing-library/jest-dom'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => { cleanup(); localStorage.clear(); document.documentElement.classList.remove('dark') })
globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia = window.matchMedia || (() => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} }))
Element.prototype.scrollIntoView = () => {}
window.print = () => {}
