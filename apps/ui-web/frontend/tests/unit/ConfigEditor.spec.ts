/**
 * Unit tests for ConfigEditor.vue - Complexity filtering
 *
 * Tests the complexity filtering functionality that shows/hides
 * configuration fields based on simple/advanced/all modes.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { mount } from '@vue/test-utils';
import ConfigEditor from '../../src/components/ConfigEditor.vue';
import type { ServiceConfig, ConfigFieldMetadata } from '../../src/types/config';

describe('ConfigEditor.vue - Complexity Filtering', () => {
  let mockConfig: ServiceConfig;

  beforeEach(() => {
    // Create mock service config with mixed complexity fields
    mockConfig = {
      service: 'test-service',
      config: {
        simple_setting: 'value1',
        advanced_setting: 'value2',
        another_simple: true,
        complex_param: 42,
      },
      version: 1,
      updatedAt: '2025-10-18T00:00:00Z',
      configEpoch: 'test-epoch-123',
      fields: [
        {
          key: 'simple_setting',
          value: 'value1',
          type: 'string',
          complexity: 'simple',
          description: 'A simple setting',
          required: false,
          source: 'database',
          envOverride: false,
        },
        {
          key: 'advanced_setting',
          value: 'value2',
          type: 'string',
          complexity: 'advanced',
          description: 'An advanced setting',
          required: false,
          source: 'database',
          envOverride: false,
        },
        {
          key: 'another_simple',
          value: true,
          type: 'boolean',
          complexity: 'simple',
          description: 'Another simple setting',
          required: false,
          source: 'database',
          envOverride: false,
        },
        {
          key: 'complex_param',
          value: 42,
          type: 'integer',
          complexity: 'advanced',
          description: 'A complex parameter',
          required: false,
          source: 'database',
          envOverride: false,
        },
      ] as ConfigFieldMetadata[],
    };
  });

  it('should show all fields when complexityFilter is "all"', () => {
    const wrapper = mount(ConfigEditor, {
      props: {
        config: mockConfig,
        complexityFilter: 'all',
        loading: false,
      },
    });

    // Should render all 4 fields
    const fields = wrapper.findAll('.config-field');
    expect(fields).toHaveLength(4);
  });

  it('should show only simple fields when complexityFilter is "simple"', () => {
    const wrapper = mount(ConfigEditor, {
      props: {
        config: mockConfig,
        complexityFilter: 'simple',
        loading: false,
      },
    });

    // Should render only 2 simple fields
    const fields = wrapper.findAll('.config-field');
    expect(fields).toHaveLength(2);

    // Verify simple fields are shown
    const fieldLabels = fields.map((f) => f.find('label').text());
    expect(fieldLabels).toContain('simple_setting');
    expect(fieldLabels).toContain('another_simple');
    expect(fieldLabels).not.toContain('advanced_setting');
    expect(fieldLabels).not.toContain('complex_param');
  });

  it('should show only advanced fields when complexityFilter is "advanced"', () => {
    const wrapper = mount(ConfigEditor, {
      props: {
        config: mockConfig,
        complexityFilter: 'advanced',
        loading: false,
      },
    });

    // Should render only 2 advanced fields
    const fields = wrapper.findAll('.config-field');
    expect(fields).toHaveLength(2);

    // Verify advanced fields are shown
    const fieldLabels = fields.map((f) => f.find('label').text());
    expect(fieldLabels).toContain('advanced_setting');
    expect(fieldLabels).toContain('complex_param');
    expect(fieldLabels).not.toContain('simple_setting');
    expect(fieldLabels).not.toContain('another_simple');
  });

  it('should handle missing field metadata with fallback', () => {
    // Config without fields metadata
    const configWithoutFields: ServiceConfig = {
      service: 'test-service',
      config: {
        setting1: 'value1',
        setting2: 42,
      },
      version: 1,
      updatedAt: '2025-10-18T00:00:00Z',
      configEpoch: 'test-epoch-123',
    };

    const wrapper = mount(ConfigEditor, {
      props: {
        config: configWithoutFields,
        complexityFilter: 'simple',
        loading: false,
      },
    });

    // Should still render fields using fallback createBasicFields()
    const fields = wrapper.findAll('.config-field');
    expect(fields.length).toBeGreaterThan(0);
  });

  it('should correctly infer field types in fallback mode', () => {
    const configWithoutFields: ServiceConfig = {
      service: 'test-service',
      config: {
        string_field: 'text',
        int_field: 42,
        float_field: 3.14,
        bool_field: true,
      },
      version: 1,
      updatedAt: '2025-10-18T00:00:00Z',
      configEpoch: 'test-epoch-123',
    };

    const wrapper = mount(ConfigEditor, {
      props: {
        config: configWithoutFields,
        complexityFilter: 'all',
        loading: false,
      },
    });

    // Check that appropriate input types are rendered
    expect(wrapper.find('input[type="text"]').exists()).toBe(true);
    expect(wrapper.find('input[type="number"]').exists()).toBe(true);
    expect(wrapper.find('input[type="checkbox"]').exists()).toBe(true);
  });

  it('should show complexity badges on fields', () => {
    const wrapper = mount(ConfigEditor, {
      props: {
        config: mockConfig,
        complexityFilter: 'all',
        loading: false,
      },
    });

    // Check for complexity badges
    const badges = wrapper.findAll('.complexity-badge');
    expect(badges.length).toBeGreaterThan(0);

    // Verify badge text
    const badgeTexts = badges.map((b) => b.text());
    expect(badgeTexts).toContain('simple');
    expect(badgeTexts).toContain('advanced');
  });

  it('should update filtered fields when complexityFilter prop changes', async () => {
    const wrapper = mount(ConfigEditor, {
      props: {
        config: mockConfig,
        complexityFilter: 'all',
        loading: false,
      },
    });

    // Initially should show all 4 fields
    expect(wrapper.findAll('.config-field')).toHaveLength(4);

    // Change to simple mode
    await wrapper.setProps({ complexityFilter: 'simple' });

    // Should now show only 2 simple fields
    expect(wrapper.findAll('.config-field')).toHaveLength(2);

    // Change to advanced mode
    await wrapper.setProps({ complexityFilter: 'advanced' });

    // Should now show only 2 advanced fields
    expect(wrapper.findAll('.config-field')).toHaveLength(2);
  });

  it('should not break when config is null', () => {
    const wrapper = mount(ConfigEditor, {
      props: {
        config: null,
        complexityFilter: 'all',
        loading: false,
      },
    });

    // Should render without crashing
    expect(wrapper.exists()).toBe(true);

    // Should show empty state or no fields
    const fields = wrapper.findAll('.config-field');
    expect(fields).toHaveLength(0);
  });

  it('should maintain field visibility consistency across re-renders', async () => {
    const wrapper = mount(ConfigEditor, {
      props: {
        config: mockConfig,
        complexityFilter: 'simple',
        loading: false,
      },
    });

    const initialFieldCount = wrapper.findAll('.config-field').length;

    // Force re-render by toggling loading
    await wrapper.setProps({ loading: true });
    await wrapper.setProps({ loading: false });

    // Field count should remain the same
    expect(wrapper.findAll('.config-field')).toHaveLength(initialFieldCount);
  });
});
