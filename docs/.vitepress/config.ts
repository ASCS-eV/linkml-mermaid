import { withMermaid } from 'vitepress-plugin-mermaid'
import { defineConfig } from 'vitepress'

// GitHub Pages serves project sites at https://<owner>.github.io/<repo>/ ,
// so the base is the repository name.
// Override with VITEPRESS_BASE if your Pages site serves from a different path.
const base = process.env.VITEPRESS_BASE ?? '/linkml-mermaid/'

const FONT =
  "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"

export default withMermaid(
  defineConfig({
    title: 'linkml-mermaid',
    description:
      'Render Mermaid diagrams and GFM tables from LinkML instance data, ' +
      'driven by annotations in the schema itself.',
    base,
    // The theme's custom.css is light-mode only, so disable the
    // dark-mode toggle rather than ship a half-themed dark appearance.
    appearance: false,
    cleanUrls: true,
    lastUpdated: true,
    themeConfig: {
      nav: [
        { text: 'Getting Started', link: '/getting-started' },
        { text: 'Architecture', link: '/architecture' },
        { text: 'Reference', link: '/annotations' },
        { text: 'Changelog', link: '/changelog' },
      ],
      sidebar: [
        {
          text: 'Introduction',
          items: [
            { text: 'Overview', link: '/' },
            { text: 'Getting Started', link: '/getting-started' },
          ],
        },
        {
          text: 'Concepts',
          items: [
            { text: 'Architecture', link: '/architecture' },
            { text: 'Flowchart Renderer', link: '/flowchart' },
          ],
        },
        {
          text: 'Reference',
          items: [
            { text: 'Annotation Vocabulary', link: '/annotations' },
            { text: 'Specification Compliance', link: '/spec-compliance' },
          ],
        },
        {
          text: 'Project',
          items: [
            { text: 'Contributing', link: '/contributing' },
            { text: 'Changelog', link: '/changelog' },
          ],
        },
      ],
      outline: { level: [2, 3] },
      socialLinks: [
        {
          icon: 'github',
          link: 'https://github.com/ASCS-eV/linkml-mermaid',
        },
      ],
      search: { provider: 'local' },
    },
    mermaid: {
      theme: 'base',
      fontFamily: FONT,
      fontSize: 16,
      securityLevel: 'loose',
      themeVariables: {
        primaryColor: '#d6e8f5',
        primaryTextColor: '#1a1a1a',
        primaryBorderColor: '#0066b1',
        secondaryColor: '#eef2f5',
        secondaryTextColor: '#1a1a1a',
        secondaryBorderColor: '#004f8a',
        tertiaryColor: '#f2f2f2',
        tertiaryTextColor: '#1a1a1a',
        tertiaryBorderColor: '#d6d6d6',
        mainBkg: '#ffffff',
        nodeBorder: '#0066b1',
        lineColor: '#6f6f6f',
        clusterBkg: '#f2f2f2',
        clusterBorder: '#d6d6d6',
        fontFamily: FONT,
        fontSize: '16px',
      },
      flowchart: {
        padding: 24,
        nodeSpacing: 64,
        rankSpacing: 80,
        htmlLabels: true,
        useMaxWidth: true,
        curve: 'basis',
      },
      themeCSS: `
        .label foreignObject div,
        .nodeLabel p {
          padding: 0.35rem 0.75rem;
          line-height: 1.35;
        }

        .node rect,
        .node polygon,
        .node circle,
        .node ellipse,
        .node path {
          stroke-width: 1.6px;
        }
      `,
    },
  })
)
