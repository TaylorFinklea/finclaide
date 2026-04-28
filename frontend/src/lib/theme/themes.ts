import type { Theme } from './types'

// Canonical palettes from the source projects:
// - Tokyo Night: github.com/folke/tokyonight.nvim
// - Catppuccin: github.com/catppuccin/catppuccin
// - Nord: nordtheme.com
// - Dracula: draculatheme.com
// - One Dark: github.com/atom/atom (one-dark-syntax)
// - Rosé Pine: rosepinetheme.com
// - Gruvbox: github.com/morhetz/gruvbox
// - Kanagawa: github.com/rebelot/kanagawa.nvim
// - Solarized: ethanschoonover.com/solarized
//
// When a theme's source palette doesn't include a clean match for one of our
// 8 accent slots we use the closest-hue color from that palette rather than
// inventing a new one — keeps every theme feeling authored.
//
// Reading order: dark themes first (most common), then light themes.

const tokyoNight: Theme = {
  id: 'tokyo-night',
  name: 'Tokyo Night',
  mode: 'dark',
  defaultAccent: 'blue',
  tokens: {
    background: '#1a1b26',
    foreground: '#c0caf5',
    card: '#1f2335',
    cardElevated: '#24283b',
    surfaceInset: '#16161e',
    popover: '#1f2335',
    popoverForeground: '#c0caf5',
    primaryForeground: '#1a1b26',
    secondary: '#292e42',
    secondaryForeground: '#c0caf5',
    muted: '#1f2335',
    mutedForeground: '#a9b1d6',
    accent: '#292e42',
    accentForeground: '#c0caf5',
    destructive: '#f7768e',
    border: '#3b4261',
    input: '#24283b',
    chart2: '#9ece6a',
    chart3: '#e0af68',
    chart4: '#f7768e',
    chart5: '#bb9af7',
    bodyGradient:
      'radial-gradient(ellipse at top left, rgb(122 162 247 / 0.08), transparent 45%), linear-gradient(180deg, #1a1b26, #16161e)',
  },
  accents: {
    blue: '#7aa2f7',
    purple: '#bb9af7',
    green: '#9ece6a',
    cyan: '#7dcfff',
    yellow: '#e0af68',
    red: '#f7768e',
    teal: '#73daca',
    orange: '#ff9e64',
  },
}

const tokyoNightStorm: Theme = {
  id: 'tokyo-night-storm',
  name: 'Tokyo Night Storm',
  mode: 'dark',
  defaultAccent: 'blue',
  tokens: {
    background: '#24283b',
    foreground: '#c0caf5',
    card: '#2a2e41',
    cardElevated: '#30354a',
    surfaceInset: '#1f2335',
    popover: '#2a2e41',
    popoverForeground: '#c0caf5',
    primaryForeground: '#24283b',
    secondary: '#343b58',
    secondaryForeground: '#c0caf5',
    muted: '#2a2e41',
    mutedForeground: '#a9b1d6',
    accent: '#343b58',
    accentForeground: '#c0caf5',
    destructive: '#f7768e',
    border: '#3b4261',
    input: '#30354a',
    chart2: '#9ece6a',
    chart3: '#e0af68',
    chart4: '#f7768e',
    chart5: '#bb9af7',
    bodyGradient:
      'radial-gradient(ellipse at top left, rgb(122 162 247 / 0.1), transparent 45%), linear-gradient(180deg, #24283b, #1f2335)',
  },
  accents: {
    blue: '#7aa2f7',
    purple: '#bb9af7',
    green: '#9ece6a',
    cyan: '#7dcfff',
    yellow: '#e0af68',
    red: '#f7768e',
    teal: '#73daca',
    orange: '#ff9e64',
  },
}

const catppuccinMocha: Theme = {
  id: 'catppuccin-mocha',
  name: 'Catppuccin Mocha',
  mode: 'dark',
  defaultAccent: 'purple',
  tokens: {
    background: '#1e1e2e',
    foreground: '#cdd6f4',
    card: '#181825',
    cardElevated: '#313244',
    surfaceInset: '#11111b',
    popover: '#181825',
    popoverForeground: '#cdd6f4',
    primaryForeground: '#1e1e2e',
    secondary: '#313244',
    secondaryForeground: '#cdd6f4',
    muted: '#181825',
    mutedForeground: '#a6adc8',
    accent: '#313244',
    accentForeground: '#cdd6f4',
    destructive: '#f38ba8',
    border: '#45475a',
    input: '#313244',
    chart2: '#a6e3a1',
    chart3: '#f9e2af',
    chart4: '#f38ba8',
    chart5: '#cba6f7',
    bodyGradient:
      'radial-gradient(ellipse at top left, rgb(203 166 247 / 0.1), transparent 45%), linear-gradient(180deg, #1e1e2e, #11111b)',
  },
  accents: {
    blue: '#89b4fa',
    purple: '#cba6f7',
    green: '#a6e3a1',
    cyan: '#89dceb',
    yellow: '#f9e2af',
    red: '#f38ba8',
    teal: '#94e2d5',
    orange: '#fab387',
  },
}

const nord: Theme = {
  id: 'nord',
  name: 'Nord',
  mode: 'dark',
  defaultAccent: 'blue',
  tokens: {
    background: '#2e3440',
    foreground: '#eceff4',
    card: '#3b4252',
    cardElevated: '#434c5e',
    surfaceInset: '#242933',
    popover: '#3b4252',
    popoverForeground: '#eceff4',
    primaryForeground: '#2e3440',
    secondary: '#434c5e',
    secondaryForeground: '#eceff4',
    muted: '#3b4252',
    mutedForeground: '#d8dee9',
    accent: '#434c5e',
    accentForeground: '#eceff4',
    destructive: '#bf616a',
    border: '#4c566a',
    input: '#434c5e',
    chart2: '#a3be8c',
    chart3: '#ebcb8b',
    chart4: '#bf616a',
    chart5: '#b48ead',
    bodyGradient:
      'radial-gradient(ellipse at top left, rgb(136 192 208 / 0.08), transparent 45%), linear-gradient(180deg, #2e3440, #242933)',
  },
  accents: {
    blue: '#81a1c1',
    purple: '#b48ead',
    green: '#a3be8c',
    cyan: '#88c0d0',
    yellow: '#ebcb8b',
    red: '#bf616a',
    teal: '#8fbcbb',
    orange: '#d08770',
  },
}

const dracula: Theme = {
  id: 'dracula',
  name: 'Dracula',
  mode: 'dark',
  defaultAccent: 'purple',
  tokens: {
    background: '#282a36',
    foreground: '#f8f8f2',
    card: '#21222c',
    cardElevated: '#44475a',
    surfaceInset: '#191a21',
    popover: '#21222c',
    popoverForeground: '#f8f8f2',
    primaryForeground: '#282a36',
    secondary: '#44475a',
    secondaryForeground: '#f8f8f2',
    muted: '#21222c',
    mutedForeground: '#bfbfd9',
    accent: '#44475a',
    accentForeground: '#f8f8f2',
    destructive: '#ff5555',
    border: '#44475a',
    input: '#44475a',
    chart2: '#50fa7b',
    chart3: '#f1fa8c',
    chart4: '#ff5555',
    chart5: '#bd93f9',
    bodyGradient:
      'radial-gradient(ellipse at top left, rgb(189 147 249 / 0.1), transparent 45%), linear-gradient(180deg, #282a36, #191a21)',
  },
  // Dracula doesn't ship a true blue — its iconic primary is purple. The
  // "blue" slot maps to the comment/grey-blue color so blue-pickers still get
  // a recognizable blue rather than a duplicated purple.
  accents: {
    blue: '#6272a4',
    purple: '#bd93f9',
    green: '#50fa7b',
    cyan: '#8be9fd',
    yellow: '#f1fa8c',
    red: '#ff5555',
    teal: '#8be9fd',
    orange: '#ffb86c',
  },
}

const oneDark: Theme = {
  id: 'one-dark',
  name: 'One Dark',
  mode: 'dark',
  defaultAccent: 'blue',
  tokens: {
    background: '#282c34',
    foreground: '#abb2bf',
    card: '#21252b',
    cardElevated: '#2c313a',
    surfaceInset: '#1e2127',
    popover: '#21252b',
    popoverForeground: '#abb2bf',
    primaryForeground: '#282c34',
    secondary: '#2c313a',
    secondaryForeground: '#abb2bf',
    muted: '#21252b',
    mutedForeground: '#828997',
    accent: '#2c313a',
    accentForeground: '#abb2bf',
    destructive: '#e06c75',
    border: '#3e4451',
    input: '#2c313a',
    chart2: '#98c379',
    chart3: '#e5c07b',
    chart4: '#e06c75',
    chart5: '#c678dd',
    bodyGradient:
      'radial-gradient(ellipse at top left, rgb(97 175 239 / 0.08), transparent 45%), linear-gradient(180deg, #282c34, #1e2127)',
  },
  accents: {
    blue: '#61afef',
    purple: '#c678dd',
    green: '#98c379',
    cyan: '#56b6c2',
    yellow: '#e5c07b',
    red: '#e06c75',
    teal: '#56b6c2',
    orange: '#d19a66',
  },
}

const rosePine: Theme = {
  id: 'rose-pine',
  name: 'Rosé Pine',
  mode: 'dark',
  defaultAccent: 'red',
  tokens: {
    background: '#191724',
    foreground: '#e0def4',
    card: '#1f1d2e',
    cardElevated: '#26233a',
    surfaceInset: '#16141f',
    popover: '#1f1d2e',
    popoverForeground: '#e0def4',
    primaryForeground: '#191724',
    secondary: '#26233a',
    secondaryForeground: '#e0def4',
    muted: '#1f1d2e',
    mutedForeground: '#908caa',
    accent: '#26233a',
    accentForeground: '#e0def4',
    destructive: '#eb6f92',
    border: '#403d52',
    input: '#26233a',
    chart2: '#9ccfd8',
    chart3: '#f6c177',
    chart4: '#eb6f92',
    chart5: '#c4a7e7',
    bodyGradient:
      'radial-gradient(ellipse at top left, rgb(235 188 186 / 0.08), transparent 45%), linear-gradient(180deg, #191724, #16141f)',
  },
  // Rosé Pine's natural palette: love (red), gold (yellow), rose (rose-pink),
  // pine (deep teal), foam (soft cyan), iris (lavender). No native green or
  // pure blue — we approximate with pine and a moss-toned blend.
  accents: {
    blue: '#31748f',
    purple: '#c4a7e7',
    green: '#56949f',
    cyan: '#9ccfd8',
    yellow: '#f6c177',
    red: '#eb6f92',
    teal: '#3e8fb0',
    orange: '#ea9d97',
  },
}

const gruvboxDark: Theme = {
  id: 'gruvbox-dark',
  name: 'Gruvbox Dark',
  mode: 'dark',
  defaultAccent: 'yellow',
  tokens: {
    background: '#282828',
    foreground: '#ebdbb2',
    card: '#3c3836',
    cardElevated: '#504945',
    surfaceInset: '#1d2021',
    popover: '#3c3836',
    popoverForeground: '#ebdbb2',
    primaryForeground: '#282828',
    secondary: '#504945',
    secondaryForeground: '#ebdbb2',
    muted: '#3c3836',
    mutedForeground: '#bdae93',
    accent: '#504945',
    accentForeground: '#ebdbb2',
    destructive: '#fb4934',
    border: '#665c54',
    input: '#504945',
    chart2: '#b8bb26',
    chart3: '#fabd2f',
    chart4: '#fb4934',
    chart5: '#d3869b',
    bodyGradient:
      'radial-gradient(ellipse at top left, rgb(250 189 47 / 0.06), transparent 45%), linear-gradient(180deg, #282828, #1d2021)',
  },
  accents: {
    blue: '#83a598',
    purple: '#d3869b',
    green: '#b8bb26',
    cyan: '#8ec07c',
    yellow: '#fabd2f',
    red: '#fb4934',
    teal: '#689d6a',
    orange: '#fe8019',
  },
}

const kanagawa: Theme = {
  id: 'kanagawa',
  name: 'Kanagawa',
  mode: 'dark',
  defaultAccent: 'blue',
  tokens: {
    background: '#1f1f28',
    foreground: '#dcd7ba',
    card: '#2a2a37',
    cardElevated: '#363646',
    surfaceInset: '#16161d',
    popover: '#2a2a37',
    popoverForeground: '#dcd7ba',
    primaryForeground: '#1f1f28',
    secondary: '#363646',
    secondaryForeground: '#dcd7ba',
    muted: '#2a2a37',
    mutedForeground: '#a6a69c',
    accent: '#363646',
    accentForeground: '#dcd7ba',
    destructive: '#c34043',
    border: '#54546d',
    input: '#363646',
    chart2: '#76946a',
    chart3: '#dca561',
    chart4: '#c34043',
    chart5: '#957fb8',
    bodyGradient:
      'radial-gradient(ellipse at top left, rgb(126 156 216 / 0.08), transparent 45%), linear-gradient(180deg, #1f1f28, #16161d)',
  },
  accents: {
    blue: '#7e9cd8',
    purple: '#957fb8',
    green: '#76946a',
    cyan: '#7fb4ca',
    yellow: '#dca561',
    red: '#c34043',
    teal: '#7aa89f',
    orange: '#ffa066',
  },
}

const catppuccinLatte: Theme = {
  id: 'catppuccin-latte',
  name: 'Catppuccin Latte',
  mode: 'light',
  defaultAccent: 'purple',
  tokens: {
    background: '#eff1f5',
    foreground: '#4c4f69',
    card: '#ffffff',
    cardElevated: '#ffffff',
    surfaceInset: '#dce0e8',
    popover: '#e6e9ef',
    popoverForeground: '#4c4f69',
    primaryForeground: '#eff1f5',
    secondary: '#dce0e8',
    secondaryForeground: '#4c4f69',
    muted: '#e6e9ef',
    mutedForeground: '#6c6f85',
    accent: '#ccd0da',
    accentForeground: '#4c4f69',
    destructive: '#d20f39',
    border: '#bcc0cc',
    input: '#ccd0da',
    chart2: '#40a02b',
    chart3: '#df8e1d',
    chart4: '#d20f39',
    chart5: '#8839ef',
    bodyGradient:
      'radial-gradient(ellipse at top left, rgb(136 57 239 / 0.06), transparent 45%), linear-gradient(180deg, #eff1f5, #e6e9ef)',
  },
  accents: {
    blue: '#1e66f5',
    purple: '#8839ef',
    green: '#40a02b',
    cyan: '#04a5e5',
    yellow: '#df8e1d',
    red: '#d20f39',
    teal: '#179299',
    orange: '#fe640b',
  },
}

const solarizedLight: Theme = {
  id: 'solarized-light',
  name: 'Solarized Light',
  mode: 'light',
  defaultAccent: 'blue',
  tokens: {
    background: '#fdf6e3',
    foreground: '#586e75',
    card: '#ffffff',
    cardElevated: '#ffffff',
    surfaceInset: '#eee8d5',
    popover: '#ffffff',
    popoverForeground: '#586e75',
    primaryForeground: '#fdf6e3',
    secondary: '#eee8d5',
    secondaryForeground: '#586e75',
    muted: '#eee8d5',
    mutedForeground: '#839496',
    accent: '#eee8d5',
    accentForeground: '#586e75',
    destructive: '#dc322f',
    border: '#d8d2bd',
    input: '#eee8d5',
    chart2: '#859900',
    chart3: '#b58900',
    chart4: '#dc322f',
    chart5: '#6c71c4',
    bodyGradient:
      'radial-gradient(ellipse at top left, rgb(38 139 210 / 0.05), transparent 45%), linear-gradient(180deg, #fdf6e3, #eee8d5)',
  },
  // Solarized doesn't ship a distinct teal — its cyan covers the blue-green
  // range and is mapped into both slots.
  accents: {
    blue: '#268bd2',
    purple: '#6c71c4',
    green: '#859900',
    cyan: '#2aa198',
    yellow: '#b58900',
    red: '#dc322f',
    teal: '#2aa198',
    orange: '#cb4b16',
  },
}

const gruvboxLight: Theme = {
  id: 'gruvbox-light',
  name: 'Gruvbox Light',
  mode: 'light',
  defaultAccent: 'orange',
  tokens: {
    background: '#fbf1c7',
    foreground: '#3c3836',
    card: '#f9f5d7',
    cardElevated: '#f9f5d7',
    surfaceInset: '#ebdbb2',
    popover: '#f9f5d7',
    popoverForeground: '#3c3836',
    primaryForeground: '#fbf1c7',
    secondary: '#ebdbb2',
    secondaryForeground: '#3c3836',
    muted: '#ebdbb2',
    mutedForeground: '#665c54',
    accent: '#ebdbb2',
    accentForeground: '#3c3836',
    destructive: '#9d0006',
    border: '#d5c4a1',
    input: '#ebdbb2',
    chart2: '#79740e',
    chart3: '#b57614',
    chart4: '#9d0006',
    chart5: '#8f3f71',
    bodyGradient:
      'radial-gradient(ellipse at top left, rgb(175 58 3 / 0.05), transparent 45%), linear-gradient(180deg, #fbf1c7, #ebdbb2)',
  },
  accents: {
    blue: '#076678',
    purple: '#8f3f71',
    green: '#79740e',
    cyan: '#427b58',
    yellow: '#b57614',
    red: '#9d0006',
    teal: '#427b58',
    orange: '#af3a03',
  },
}

export const THEMES: Theme[] = [
  tokyoNight,
  tokyoNightStorm,
  catppuccinMocha,
  nord,
  dracula,
  oneDark,
  rosePine,
  gruvboxDark,
  kanagawa,
  catppuccinLatte,
  solarizedLight,
  gruvboxLight,
]

export const THEMES_BY_ID: Record<string, Theme> = Object.fromEntries(
  THEMES.map((theme) => [theme.id, theme]),
)

export const DEFAULT_THEME_ID = 'tokyo-night'

export function getTheme(id: string | null | undefined): Theme {
  if (id && THEMES_BY_ID[id]) {
    return THEMES_BY_ID[id]
  }
  return THEMES_BY_ID[DEFAULT_THEME_ID]
}
