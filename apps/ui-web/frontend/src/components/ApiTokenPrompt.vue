<template>
  <div v-if="showPrompt" class="token-prompt-overlay">
    <div class="token-prompt-dialog">
      <div class="token-prompt-header">
        <h2>🔐 API Authentication Required</h2>
        <p>Enter your API token to access configuration management</p>
      </div>
      
      <form @submit.prevent="handleSubmit" class="token-prompt-form">
        <div class="form-group">
          <label for="api-token">API Token:</label>
          <input
            id="api-token"
            v-model="tokenInput"
            type="password"
            placeholder="Enter your MQTT password or API token"
            autocomplete="off"
            autofocus
            :disabled="isVerifying"
          />
          <small class="hint">Default: Your MQTT password (check .env file)</small>
        </div>

        <div v-if="error" class="error-message">
          {{ error }}
        </div>

        <div class="button-group">
          <button 
            type="submit" 
            class="btn btn-primary"
            :disabled="!tokenInput || isVerifying"
          >
            {{ isVerifying ? 'Verifying...' : 'Connect' }}
          </button>
        </div>
      </form>

      <div class="token-prompt-footer">
        <details>
          <summary>Where do I find my API token?</summary>
          <div class="help-content">
            <p><strong>Default Token:</strong> Your MQTT password from <code>.env</code> file</p>
            <p><strong>Check logs:</strong></p>
            <pre>docker compose logs config-manager | grep "API token"</pre>
            <p><strong>Custom Token:</strong> Set <code>API_TOKENS</code> in your <code>.env</code> file</p>
          </div>
        </details>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useConfig } from '../composables/useConfig';

const { setApiToken, detectUserRole } = useConfig();

const showPrompt = ref(false);
const tokenInput = ref('');
const error = ref('');
const isVerifying = ref(false);

// Check if token exists in localStorage
onMounted(() => {
  const existingToken = localStorage.getItem('api_token');
  if (!existingToken) {
    showPrompt.value = true;
  }
});

async function handleSubmit() {
  if (!tokenInput.value) {
    error.value = 'Please enter an API token';
    return;
  }

  error.value = '';
  isVerifying.value = true;

  try {
    // Set the token
    setApiToken(tokenInput.value);

    // Try to verify it by detecting user role (makes API call)
    await detectUserRole();

    // If we get here, token is valid
    showPrompt.value = false;
    tokenInput.value = '';
    
    // Emit event to parent that token is set
    emits('tokenSet');
    
  } catch (err) {
    error.value = 'Invalid token or connection failed. Please try again.';
    // Clear the invalid token
    localStorage.removeItem('api_token');
  } finally {
    isVerifying.value = false;
  }
}

const emits = defineEmits<{
  tokenSet: []
}>();

// Expose method to show prompt again if needed
defineExpose({
  show: () => { showPrompt.value = true; }
});
</script>

<style scoped>
.token-prompt-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 20px;
}

.token-prompt-dialog {
  background: var(--bg-secondary, #1a1a1a);
  border: 1px solid var(--border-color, #333);
  border-radius: 12px;
  max-width: 500px;
  width: 100%;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.token-prompt-header {
  padding: 24px 24px 16px;
  border-bottom: 1px solid var(--border-color, #333);
}

.token-prompt-header h2 {
  margin: 0 0 8px 0;
  font-size: 1.5rem;
  color: var(--text-primary, #fff);
}

.token-prompt-header p {
  margin: 0;
  color: var(--text-secondary, #aaa);
  font-size: 0.9rem;
}

.token-prompt-form {
  padding: 24px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: var(--text-primary, #fff);
}

.form-group input {
  width: 100%;
  padding: 12px;
  background: var(--bg-primary, #0f0f0f);
  border: 1px solid var(--border-color, #333);
  border-radius: 6px;
  color: var(--text-primary, #fff);
  font-size: 1rem;
  font-family: monospace;
  transition: border-color 0.2s;
}

.form-group input:focus {
  outline: none;
  border-color: var(--accent-color, #00d4ff);
  box-shadow: 0 0 0 3px rgba(0, 212, 255, 0.1);
}

.form-group input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.hint {
  display: block;
  margin-top: 6px;
  color: var(--text-secondary, #888);
  font-size: 0.85rem;
}

.error-message {
  padding: 12px;
  background: rgba(255, 59, 48, 0.1);
  border: 1px solid rgba(255, 59, 48, 0.3);
  border-radius: 6px;
  color: #ff3b30;
  margin-bottom: 16px;
  font-size: 0.9rem;
}

.button-group {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.btn {
  padding: 10px 24px;
  border: none;
  border-radius: 6px;
  font-size: 1rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary {
  background: var(--accent-color, #00d4ff);
  color: #000;
}

.btn-primary:hover:not(:disabled) {
  background: var(--accent-hover, #00b8e6);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 212, 255, 0.3);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.token-prompt-footer {
  padding: 16px 24px;
  background: var(--bg-tertiary, #111);
  border-top: 1px solid var(--border-color, #333);
  border-radius: 0 0 12px 12px;
}

details {
  cursor: pointer;
}

summary {
  font-size: 0.9rem;
  color: var(--text-secondary, #aaa);
  user-select: none;
}

summary:hover {
  color: var(--accent-color, #00d4ff);
}

.help-content {
  margin-top: 12px;
  padding: 12px;
  background: var(--bg-primary, #0f0f0f);
  border-radius: 6px;
  font-size: 0.85rem;
}

.help-content p {
  margin: 8px 0;
  color: var(--text-secondary, #aaa);
}

.help-content strong {
  color: var(--text-primary, #fff);
}

.help-content code {
  background: var(--bg-secondary, #1a1a1a);
  padding: 2px 6px;
  border-radius: 3px;
  font-family: monospace;
  color: var(--accent-color, #00d4ff);
}

.help-content pre {
  background: var(--bg-secondary, #1a1a1a);
  padding: 8px;
  border-radius: 4px;
  overflow-x: auto;
  margin: 8px 0;
  color: var(--text-secondary, #aaa);
  font-size: 0.8rem;
}
</style>
