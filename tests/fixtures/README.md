# Synthetic fixtures

All businesses, domains and pages in automated tests are explicitly synthetic. `.example.test` is used in isolated test databases/mocked responses; no competitor research has occurred. Tests do not seed invented analytics into the running application database.

The optional WordPress/MariaDB fixture runs at localhost:8081, has a persistent DEMO label, uses randomly generated local credentials, and retains blog_public=0. Its custom theme supports core title-tag/wp_head hooks. No Elementor/Pro installation or body-widget compatibility is claimed. The plugin fixture test verifies a known SEO-provider conflict with a synthetic constant rather than claiming a real Yoast integration test.
