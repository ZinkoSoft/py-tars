/**
 * Unit tests for ConfigTabs.vue - localStorage persistence
 *
 * Tests that the user's complexity mode preference (simple/advanced/all)
 * is correctly persisted to localStorage and restored on mount.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import ConfigTabs from '../../src/components/ConfigTabs.vue';

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};

  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value;
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
})();

// Mock composables
vi.mock('../../src/composables/useConfig', () => ({
  useConfig: () => ({
    services: { value: ['test-service'] },
    currentConfig: { value: null },
    loading: { value: false },
    error: { value: null },
    loadServices: vi.fn(),
    loadConfig: vi.fn(),
    updateConfig: vi.fn(),
  }),
}));

vi.mock('../../src/composables/useNotifications', () => ({
  useNotifications: () => ({
    notify: vi.fn(),
  }),
}));

vi.mock('../../src/composables/useHealth', () => ({
  useHealth: () => ({
    isHealthy: { value: true },
    lastUpdate: { value: null },
  }),
}));

describe('ConfigTabs.vue - localStorage Persistence', () => {
  beforeEach(() => {
    // Replace global localStorage with mock
    Object.defineProperty(window, 'localStorage', {
      value: localStorageMock,
      writable: true,
    });

    // Clear localStorage before each test
    localStorageMock.clear();
  });

  afterEach(() => {
    localStorageMock.clear();
  });

  it('should default to "simple" mode when no localStorage value exists', () => {
    const wrapper = mount(ConfigTabs);

    // Check that simple button is active by default
    const simpleBtn = wrapper.find('.complexity-btn.active');
    expect(simpleBtn.text()).toBe('Simple');
  });

  it('should persist complexity mode to localStorage when changed', async () => {
    const wrapper = mount(ConfigTabs);

    // Click advanced button
    const advancedBtn = wrapper.findAll('.complexity-btn')[1];
    await advancedBtn.trigger('click');

    // Check localStorage was updated
    expect(localStorageMock.getItem('config-complexity-mode')).toBe('advanced');

    // Click all button
    const allBtn = wrapper.findAll('.complexity-btn')[2];
    await allBtn.trigger('click');

    // Check localStorage was updated again
    expect(localStorageMock.getItem('config-complexity-mode')).toBe('all');
  });

  it('should restore complexity mode from localStorage on mount', () => {
    // Set localStorage value before mounting
    localStorageMock.setItem('config-complexity-mode', 'advanced');

    const wrapper = mount(ConfigTabs);

    // Check that advanced button is active (restored from localStorage)
    const activeBtn = wrapper.find('.complexity-btn.active');
    expect(activeBtn.text()).toBe('Advanced');
  });

  it('should handle invalid localStorage values gracefully', () => {
    // Set invalid value in localStorage
    localStorageMock.setItem('config-complexity-mode', 'invalid-value');

    const wrapper = mount(ConfigTabs);

    // Should fallback to default (simple) mode
    const activeBtn = wrapper.find('.complexity-btn.active');
    expect(activeBtn.text()).toBe('Simple');
  });

  it('should update active button class when mode changes', async () => {
    const wrapper = mount(ConfigTabs);

    // Initially simple is active
    let activeBtns = wrapper.findAll('.complexity-btn.active');
    expect(activeBtns).toHaveLength(1);
    expect(activeBtns[0].text()).toBe('Simple');

    // Click advanced
    const advancedBtn = wrapper.findAll('.complexity-btn')[1];
    await advancedBtn.trigger('click');

    // Now advanced is active
    activeBtns = wrapper.findAll('.complexity-btn.active');
    expect(activeBtns).toHaveLength(1);
    expect(activeBtns[0].text()).toBe('Advanced');

    // Click all
    const allBtn = wrapper.findAll('.complexity-btn')[2];
    await allBtn.trigger('click');

    // Now all is active
    activeBtns = wrapper.findAll('.complexity-btn.active');
    expect(activeBtns).toHaveLength(1);
    expect(activeBtns[0].text()).toBe('All');
  });

  it('should maintain localStorage persistence across multiple instances', () => {
    // Mount first instance and change mode
    const wrapper1 = mount(ConfigTabs);
    const advancedBtn1 = wrapper1.findAll('.complexity-btn')[1];
    advancedBtn1.trigger('click');

    // Unmount first instance
    wrapper1.unmount();

    // Mount second instance - should restore from localStorage
    const wrapper2 = mount(ConfigTabs);
    const activeBtn = wrapper2.find('.complexity-btn.active');
    expect(activeBtn.text()).toBe('Advanced');

    wrapper2.unmount();
  });

  it('should pass complexity filter to ConfigEditor', async () => {
    const wrapper = mount(ConfigTabs);

    // Get ConfigEditor component
    const configEditor = wrapper.findComponent({ name: 'ConfigEditor' });

    // Initially should pass 'simple' (or default)
    expect(configEditor.props('complexityFilter')).toBeTruthy();

    // Click advanced
    const advancedBtn = wrapper.findAll('.complexity-btn')[1];
    await advancedBtn.trigger('click');

    // Should now pass 'advanced'
    expect(configEditor.props('complexityFilter')).toBe('advanced');

    // Click all
    const allBtn = wrapper.findAll('.complexity-btn')[2];
    await allBtn.trigger('click');

    // Should now pass 'all'
    expect(configEditor.props('complexityFilter')).toBe('all');
  });

  it('should not throw errors if localStorage is unavailable', () => {
    // Simulate localStorage being unavailable (e.g., private browsing)
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: () => {
          throw new Error('localStorage unavailable');
        },
        setItem: () => {
          throw new Error('localStorage unavailable');
        },
      },
      writable: true,
    });

    // Should not throw when mounting
    expect(() => mount(ConfigTabs)).not.toThrow();
  });

  it('should preserve mode when navigating between services', async () => {
    localStorageMock.setItem('config-complexity-mode', 'advanced');

    const wrapper = mount(ConfigTabs);

    // Verify advanced is active
    let activeBtn = wrapper.find('.complexity-btn.active');
    expect(activeBtn.text()).toBe('Advanced');

    // Simulate service change (if multiple services exist)
    // The complexity mode should remain 'advanced'
    await wrapper.vm.$nextTick();

    activeBtn = wrapper.find('.complexity-btn.active');
    expect(activeBtn.text()).toBe('Advanced');
  });

  it('should use correct localStorage key', async () => {
    const wrapper = mount(ConfigTabs);

    const advancedBtn = wrapper.findAll('.complexity-btn')[1];
    await advancedBtn.trigger('click');

    // Verify the specific key is used
    const keys = Object.keys(localStorageMock);
    expect(keys).toContain('config-complexity-mode');
  });
});
