<template>
  <div class="shell-wrap">
    <aside class="shell-rail">
      <div class="rail-brand">
        <p class="brand-cn">创新创业智能体</p>
        <p class="brand-en">Venture Atelier</p>
      </div>

      <div class="rail-user">
        <p class="label">当前用户</p>
        <p class="value">{{ user?.name || user?.full_name || user?.username || '未登录' }}</p>
        <p class="muted">{{ roleLabel }}</p>
      </div>

      <nav class="rail-nav" aria-label="主导航">
        <RouterLink
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-entry"
          :class="{ active: route.path === item.path }"
        >
          <span class="dot" aria-hidden="true"></span>
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <button type="button" class="rail-logout" @click="$emit('logout')">退出登录</button>
    </aside>

    <section class="shell-stage">
      <header class="stage-head">
        <div class="stage-head-row">
          <div>
            <h1>{{ title }}</h1>
            <p>{{ subtitle }}</p>
          </div>
          <button type="button" class="head-logout" @click="$emit('logout')">退出登录</button>
        </div>
      </header>
      <main id="app-main" class="stage-content">
        <slot />
      </main>
    </section>
  </div>
</template>

<script setup>
import { useRoute, RouterLink } from 'vue-router';

defineProps({
  user: {
    type: Object,
    default: null
  },
  roleLabel: {
    type: String,
    default: '访客'
  },
  title: {
    type: String,
    default: ''
  },
  subtitle: {
    type: String,
    default: ''
  },
  navItems: {
    type: Array,
    default: () => []
  }
});

defineEmits(['logout']);

const route = useRoute();
</script>

<style scoped>
.shell-wrap {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(276px, 304px) minmax(0, 1fr);
  background: var(--bg-main);
}

.shell-rail {
  border-right: 1px solid color-mix(in oklch, var(--line-soft) 82%, white);
  background:
    radial-gradient(150% 62% at -24% -12%, color-mix(in oklch, var(--accent) 16%, transparent), transparent 62%),
    linear-gradient(184deg, color-mix(in oklch, var(--bg-rail) 78%, white), color-mix(in oklch, var(--bg-rail) 96%, white)),
    var(--bg-rail);
  padding: 26px 18px 18px;
  display: grid;
  grid-template-rows: auto auto 1fr auto;
  gap: 16px;
  position: sticky;
  top: 0;
  height: 100vh;
  box-shadow:
    inset -1px 0 0 color-mix(in oklch, var(--line-soft) 68%, white),
    14px 0 30px color-mix(in oklch, var(--accent) 14%, transparent);
}

.rail-brand .brand-cn {
  margin: 0;
  font-family: var(--font-display);
  font-size: 24px;
  letter-spacing: 0.026em;
  font-weight: 760;
  color: var(--ink-title);
  line-height: 1.2;
}

.rail-brand .brand-en {
  margin: 5px 0 0;
  font-size: 11px;
  color: var(--ink-muted);
  text-transform: uppercase;
  letter-spacing: 0.14em;
}

.rail-user {
  border: 1px solid color-mix(in oklch, var(--line-soft) 76%, white);
  border-radius: 16px;
  padding: 13px 13px 12px;
  background:
    linear-gradient(155deg, color-mix(in oklch, var(--accent) 8%, white), color-mix(in oklch, var(--bg-panel) 97%, white));
  box-shadow: 0 12px 22px color-mix(in oklch, var(--accent) 11%, transparent);
}

.rail-user .label {
  margin: 0;
  font-size: 12px;
  color: var(--ink-muted);
}

.rail-user .value {
  margin: 7px 0 0;
  font-family: var(--font-display);
  font-size: 19px;
  font-weight: 760;
  color: var(--ink-title);
  line-height: 1.28;
  word-break: break-word;
}

.rail-user .muted {
  margin: 6px 0 0;
  color: var(--ink-muted);
  font-size: 12px;
}

.rail-nav {
  display: grid;
  align-content: start;
  gap: 7px;
  overflow-y: auto;
  padding: 2px 3px 2px 0;
}

.nav-entry {
  display: flex;
  align-items: center;
  gap: 11px;
  min-height: 44px;
  padding: 8px 12px;
  text-decoration: none;
  color: var(--ink-body);
  border: 1px solid color-mix(in oklch, var(--line-soft) 66%, transparent);
  border-radius: 14px;
  background: color-mix(in oklch, var(--bg-panel) 66%, white);
  font-size: 14px;
  font-weight: 640;
  transition:
    border-color var(--motion-fast) ease,
    background var(--motion-fast) ease,
    transform var(--motion-fast) cubic-bezier(0.22, 0.7, 0.18, 1),
    box-shadow var(--motion-mid) ease;
}

.nav-entry .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: color-mix(in oklch, var(--line-strong) 75%, white);
  transition: transform var(--motion-fast) ease, background var(--motion-fast) ease;
}

.nav-entry:hover {
  border-color: color-mix(in oklch, var(--accent) 45%, var(--line-strong));
  background: color-mix(in oklch, var(--accent) 12%, white);
  transform: translateX(2px) translateY(-1px);
  box-shadow: 0 9px 18px color-mix(in oklch, var(--accent) 16%, transparent);
}

.nav-entry:hover .dot {
  transform: scale(1.3);
  background: color-mix(in oklch, var(--accent) 75%, white);
}

.nav-entry.active {
  border-color: color-mix(in oklch, var(--accent) 72%, var(--line-strong));
  color: var(--ink-title);
  background: color-mix(in oklch, var(--accent) 18%, white);
  box-shadow:
    inset 0 0 0 1px color-mix(in oklch, var(--accent) 44%, white),
    0 10px 22px color-mix(in oklch, var(--accent) 24%, transparent);
}

.nav-entry.active .dot {
  background: var(--accent);
  transform: scale(1.36);
}

.rail-logout {
  appearance: none;
  border: 1px solid color-mix(in oklch, var(--danger) 64%, var(--line-strong));
  background: color-mix(in oklch, var(--bg-panel) 92%, white);
  color: var(--ink-title);
  height: 38px;
  padding: 0 14px;
  cursor: pointer;
  border-radius: 999px;
}

.rail-logout:hover {
  border-color: var(--danger);
  color: var(--danger);
  transform: translateY(-1px);
}

.rail-logout:focus-visible {
  outline: none;
  box-shadow: var(--shadow-focus);
}

.shell-stage {
  padding: 18px clamp(14px, 2.8vw, 38px) 30px;
  display: grid;
  grid-template-rows: auto 1fr;
  gap: 16px;
  min-height: 100vh;
  min-width: 0;
}

.stage-content {
  min-width: 0;
  display: grid;
  gap: 16px;
  width: min(1480px, 100%);
  margin: 0 auto;
}

.stage-head {
  border: 1px solid color-mix(in oklch, var(--line-soft) 78%, white);
  padding: 15px 17px;
  border-radius: 16px;
  box-shadow: var(--shadow-soft);
  position: sticky;
  top: 0;
  z-index: 20;
  background:
    linear-gradient(
      126deg,
      color-mix(in oklch, var(--accent) 11%, white),
      color-mix(in oklch, var(--bg-panel) 98%, white) 34%,
      color-mix(in oklch, var(--accent-2) 8%, white)
    );
  backdrop-filter: blur(10px);
}

.stage-head-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.stage-head h1 {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--font-size-hero);
  letter-spacing: 0.018em;
  font-weight: 780;
  color: var(--ink-title);
  line-height: var(--line-height-tight);
}

.stage-head p {
  margin: 7px 0 0;
  color: var(--ink-body);
  max-width: 60ch;
  font-size: var(--font-size-md);
  line-height: var(--line-height-loose);
}

.head-logout {
  appearance: none;
  border: 1px solid color-mix(in oklch, var(--danger) 60%, var(--line-strong));
  background: color-mix(in oklch, var(--bg-panel) 90%, white);
  color: var(--danger);
  height: 36px;
  padding: 0 14px;
  border-radius: 999px;
  cursor: pointer;
  transition: transform 0.16s ease, border-color 0.16s ease;
}

.head-logout:hover {
  border-color: var(--danger);
  background: color-mix(in oklch, var(--danger) 8%, white);
  transform: translateY(-1px);
}

.head-logout:focus-visible {
  outline: none;
  box-shadow: var(--shadow-focus);
}

@media (max-width: 980px) {
  .shell-wrap {
    grid-template-columns: 1fr;
  }

  .shell-rail {
    border-right: none;
    border-bottom: 1px solid color-mix(in oklch, var(--line-soft) 90%, white);
    grid-template-rows: auto auto auto;
    position: sticky;
    top: 0;
    height: auto;
    box-shadow: 0 8px 20px color-mix(in oklch, var(--accent) 10%, transparent);
    z-index: 30;
    padding: 14px 12px 12px;
    gap: 12px;
  }

  .rail-nav {
    display: flex;
    flex-wrap: nowrap;
    overflow-x: auto;
    overflow-y: hidden;
    padding: 0 2px 6px 0;
    gap: 8px;
    scrollbar-width: thin;
  }

  .nav-entry {
    min-width: max-content;
    min-height: 42px;
    padding: 8px 12px;
  }

  .stage-head {
    position: static;
    backdrop-filter: none;
  }

  .stage-head-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }

  .head-logout {
    width: 100%;
    min-height: var(--touch-target);
  }
}

@media (max-width: 640px) {
  .rail-brand .brand-cn {
    font-size: 21px;
  }

  .rail-user .value {
    font-size: 17px;
  }

  .shell-stage {
    padding: 12px 10px 20px;
    gap: 12px;
  }

  .stage-head {
    padding: 12px;
    border-radius: 14px;
  }
}
</style>
