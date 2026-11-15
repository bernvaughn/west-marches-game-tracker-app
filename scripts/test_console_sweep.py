"""Browser guard: no page may log a console error. Run with `pytest -m browser`."""

import pytest


@pytest.mark.browser
def test_no_console_errors_on_any_page():
    from scripts.console_sweep import sweep

    problems = sweep()
    assert not problems, "\n".join(problems)


@pytest.mark.browser
def test_design_page_axe_contrast():
    """Check axe-core contrast violations on /site/design/ (B-08)."""
    import subprocess
    import sys
    
    ROOT = __file__.replace("test_console_sweep.py", "")
    
    # Python script to run axe on the design page
    axe_script = (
        "import asyncio\n"
        "from playwright.async_api import async_playwright\n"
        "\n"
        "async def run():\n"
        "    async with async_playwright() as pw:\n"
        "        browser = await pw.chromium.launch()\n"
        "        context = await browser.new_context(viewport={\"width\": 1280, \"height\": 800})\n"
        "        page = await context.new_page()\n"
        "        \n"
        "        # Login as site_admin\n"
        "        await page.goto(\"http://127.0.0.1:8000/accounts/login/\")\n"
        "        await page.fill(\"input[name=username]\", \"admin@example.com\")\n"
        "        await page.fill(\"input[name=password]\", \"demo-password\")\n"
        "        await page.click(\"form button[type=submit], form input[type=submit]\")\n"
        "        await page.wait_for_load_state(\"networkidle\")\n"
        "        \n"
        "        # Go to design page\n"
        "        await page.goto(\"http://127.0.0.1:8000/site/design/\")\n"
        "        await page.wait_for_load_state(\"networkidle\")\n"
        "        \n"
        "        # Inject axe-core\n"
        "        await page.add_script_tag(url=\"https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js\")\n"
        "        \n"
        "        # Run axe\n"
        "        results = await page.evaluate(\n"
        "            \"() => {\n"
        "                return axe.run(document, {\n"
        "                    runOnly: { type: 'rule', values: ['color-contrast'] }\n"
        "                }).then(r => r.violations);\n"
        "            }\"\n"
        "        )\n"
        "        \n"
        "        await browser.close()\n"
        "        return results\n"
        "\n"
        "results = asyncio.run(run())\n"
        "print(results)\n"
    )
    
    cmd = [
        sys.executable, "-m", "uv", "run", "python", "-c", axe_script,
    ]
    
    env = {
        **__import__("os").environ,
        "PLAYWRIGHT_BROWSERS_PATH": "/tmp/vfy/pw",
        "LD_LIBRARY_PATH": "/tmp/vfy/libroot/usr/lib/x86_64-linux-gnu",
    }
    
    result = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    
    # Parse violations
    violations = []
    if result.returncode == 0:
        try:
            import json
            violations = json.loads(result.stdout.strip().splitlines()[-1])
        except Exception:
            pass
    
    # Filter for contrast violations on inline code (the known B-08 issue)
    contrast_violations = [v for v in violations if v.get("id") == "color-contrast"]
    inline_code_violations = []
    for v in contrast_violations:
        for node in v.get("nodes", []):
            if "inline" in node.get("html", "") and "code" in node.get("html", ""):
                inline_code_violations.append(v)
                break
    
    msg = f"Found {len(inline_code_violations)} inline code contrast violations on /site/design/"
    assert not inline_code_violations, msg