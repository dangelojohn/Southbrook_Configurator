#!/usr/bin/env python3
"""Headless-browser customer-flow smoke for southbrookcabinetry.local.

The curl-based smoke (scripts/smoke_customer_flow.sh) verifies HTTP
routes + JSON-RPC + DB state. It cannot catch:

    OWL mount failures           (QWeb chain breaks, t-elif/else)
    JS console errors            (Uncaught TypeError on click)
    OWL module-load failures     (xml(...).bind is not a function)
    CSS-driven visibility        (form rendered but d-none'd)

This script does. It loads each page in headless Chromium, listens
for console errors + page exceptions, and clicks through the
add-cabinet → configure → request-price flow. Any uncaught
exception fails the test.

Today's bug history this script would have caught:
    1b598bb  CatalogPicker QWeb chain    →  OWL mount fail on load
    aa31077  PLM cut.spec AccessError    →  500 on /api/order/<id> XHR
    ba8cc1a  Method props missing .bind  →  TypeError on tile click
    a9b0297  Login form hidden by d-none →  visible form element check
    f893d9e  .bind directive miscompile  →  TypeError xml(...).bind
    dbbfa15  This commit's setup() fix  →  (verifies the fix works)

Run with:
    /tmp/sb-pw-venv/bin/python scripts/smoke_browser.py

Exits 0 on full success; 1 with details on any console error /
exception / missing-element assertion.
"""
import asyncio
import re
import sys
import time
from playwright.async_api import async_playwright, Page

HOST = "https://www.southbrookcabinetry.local:9443"
RESOLVE = "192.168.68.108:9443"  # MAP target

PASSES = []
FAILS = []


def passed(desc):
    PASSES.append(desc)
    print(f"  ✓ {desc}")


def failed(desc, detail=""):
    FAILS.append(f"{desc} :: {detail}" if detail else desc)
    print(f"  ✗ {desc}  {detail}")


class PageProbe:
    """Attach console + pageerror listeners that pump into a shared list."""

    def __init__(self, page: Page, label: str):
        self.page = page
        self.label = label
        self.errors = []  # list of dicts {type, text}

        def on_console(msg):
            if msg.type in ("error", "warning"):
                self.errors.append({"type": f"console.{msg.type}", "text": msg.text})

        def on_pageerror(exc):
            self.errors.append({"type": "pageerror", "text": str(exc)})

        page.on("console", on_console)
        page.on("pageerror", on_pageerror)

    def fatal_errors(self):
        """Filter out known-noisy warnings; return only fatal-grade errors."""
        keep = []
        for e in self.errors:
            t = e["text"]
            # Ignore three.js deprecation noise — known + tracked.
            if "deprecated" in t.lower() and "three" in t.lower():
                continue
            # Ignore 401 noise from anonymous API probes during page boot
            if "401" in t and "api" in t.lower():
                continue
            keep.append(e)
        return keep


async def run():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                f"--host-resolver-rules=MAP www.southbrookcabinetry.local:9443 {RESOLVE}",
                "--ignore-certificate-errors",
            ],
        )
        ctx = await browser.new_context(ignore_https_errors=True)

        # ----------------------------------------------------------------
        # 1. Anonymous /
        # ----------------------------------------------------------------
        print()
        print("[/] Anonymous homepage")
        page = await ctx.new_page()
        probe = PageProbe(page, "/")
        try:
            await page.goto(f"{HOST}/", wait_until="networkidle", timeout=15000)
        except Exception as e:
            failed("/ navigation", str(e))
        else:
            title = await page.title()
            if "Southbrook" in title:
                passed("title contains Southbrook")
            else:
                failed("title", f"got '{title}'")
            hero = await page.locator(".o_sb_hero_title").count()
            if hero >= 1:
                passed(f"hero title element present ({hero})")
            else:
                failed("hero title", "0 .o_sb_hero_title elements")
            cta = await page.locator(
                "a.o_sb_btn_primary:has-text('Design Your Kitchen')"
            ).count()
            if cta >= 1:
                passed(f"'Design Your Kitchen' CTA visible ({cta})")
            else:
                failed("Design Your Kitchen CTA", f"{cta}")
        fatal = probe.fatal_errors()
        if fatal:
            for e in fatal:
                failed("console error on /", f"{e['type']}: {e['text'][:200]}")
        else:
            passed("/ has no fatal console errors")
        await page.close()

        # ----------------------------------------------------------------
        # 2. /web/login
        # ----------------------------------------------------------------
        print()
        print("[/web/login] Branded login form")
        page = await ctx.new_page()
        probe = PageProbe(page, "/web/login")
        try:
            await page.goto(f"{HOST}/web/login", wait_until="networkidle", timeout=15000)
        except Exception as e:
            failed("/web/login navigation", str(e))
        else:
            email = page.locator('input[name="login"]')
            pwd = page.locator('input[name="password"]')
            visible_email = await email.is_visible()
            visible_pwd = await pwd.is_visible()
            if visible_email:
                passed("email input is visible")
            else:
                failed("email input visible", "not visible / hidden by d-none")
            if visible_pwd:
                passed("password input is visible")
            else:
                failed("password input visible", "not visible / hidden by d-none")
        fatal = probe.fatal_errors()
        if fatal:
            for e in fatal:
                failed("console error on /web/login", f"{e['type']}: {e['text'][:200]}")
        else:
            passed("/web/login has no fatal console errors")
        await page.close()

        # ----------------------------------------------------------------
        # 3. Sign up + portal order-builder add-cabinet
        # ----------------------------------------------------------------
        print()
        print("[full customer flow] sign up, mount Order Builder, add cabinet")
        ts = int(time.time())
        email = f"pw{ts}@s.test"
        page = await ctx.new_page()
        probe = PageProbe(page, "order-builder full flow")
        try:
            # Pass the post-signup redirect via querystring so the
            # qcontext picks it up (the hidden form input can't be
            # fill()-ed because Playwright requires visible inputs).
            redirect = "/my/southbrook/order-builder/new"
            await page.goto(
                f"{HOST}/web/signup?redirect={redirect}",
                wait_until="networkidle", timeout=15000,
            )
            await page.fill('input[name="name"]', "Playwright User")
            await page.fill('input[name="login"]', email)
            await page.fill('input[name="project_name"]', f"PW Test {ts}")
            await page.fill('input[name="password"]', "demo12345!")
            await page.fill('input[name="confirm_password"]', "demo12345!")
            # Target the signup form's submit button specifically — there
            # are 3 type=submit buttons on the page (searchbar, signup,
            # password-toggle inside the form).
            await page.locator(
                "form.oe_signup_form button[type='submit']"
            ).click()
            # Wait for redirect to the order builder page.
            await page.wait_for_url(
                re.compile(r"/my/southbrook/order-builder/\d+"),
                timeout=15000,
            )
            passed(f"signup redirected to {page.url[-60:]}")
        except Exception as e:
            failed("signup flow", str(e)[:200])
            await page.close()
            await ctx.close()
            await browser.close()
            return

        try:
            # Wait for OWL to mount the empty state.
            await page.wait_for_selector(
                "button.o_owl_add_cabinet_lg, .o_owl_lines_empty",
                timeout=15000,
            )
            passed("OWL Order Builder mounted (empty-state visible)")
        except Exception as e:
            failed("OWL mount", f"empty state never rendered: {str(e)[:120]}")

        # Click "+ Add Your First Cabinet" — this is the click chain that
        # broke today across 3 fix attempts.
        try:
            await page.click("button.o_owl_add_cabinet_lg", timeout=5000)
            await page.wait_for_selector(
                ".o_owl_modal_panel.o_owl_catalog_panel",
                timeout=5000,
            )
            passed("CatalogPicker modal opens")
        except Exception as e:
            failed("CatalogPicker open", str(e)[:120])

        # Wait for the async catalog RPC to populate the card grid
        # before asserting count.
        #
        # 2026-06-02 redesign: .o_owl_catalog_tile (old whole-card
        # click target) was replaced by .o_owl_catalog_card with a
        # dedicated .o_owl_catalog_add_btn per card. The card itself
        # is no longer the click target — the Add button is.
        try:
            await page.wait_for_selector(
                ".o_owl_catalog_card", timeout=10000,
            )
        except Exception as e:
            failed("catalog cards wait", str(e)[:120])
        card_count = await page.locator(".o_owl_catalog_card").count()
        if card_count >= 10:
            passed(f"{card_count} catalog cards rendered (expect 12)")
        else:
            failed("catalog cards", f"only {card_count}")

        # Click the FIRST card's Add button (SB-BASE-1DR after the
        # logical sort: All / Base / Wall / Tall / Drawer / Vanity /
        # Extras + the catalog xml_id order within Base). This is THE
        # click that crashed with 'this.state undefined' until the
        # setup() bind fix; the harness keeps it as a regression
        # guard against future bind-context regressions.
        try:
            await page.locator(
                ".o_owl_catalog_card .o_owl_catalog_add_btn"
            ).first.click(timeout=5000)
            await page.wait_for_selector(
                ".o_owl_lines_topbar",
                timeout=8000,
            )
            passed("cabinet added — lines topbar appeared (no TypeError)")
        except Exception as e:
            failed("add cabinet click chain", str(e)[:200])

        fatal = probe.fatal_errors()
        if fatal:
            for e in fatal:
                failed("console error during click chain",
                       f"{e['type']}: {e['text'][:200]}")
        else:
            passed("full click chain — no fatal console errors")
        await page.close()

        await ctx.close()
        await browser.close()


def main():
    print("=" * 64)
    print(" Headless-browser smoke (scripts/smoke_browser.py)")
    print("=" * 64)
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("(interrupted)")
        sys.exit(2)
    print()
    print("=" * 64)
    print(f" Summary: {len(PASSES)} passed · {len(FAILS)} failed")
    print("=" * 64)
    if FAILS:
        print()
        for f in FAILS:
            print(f"  ✗ {f}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
