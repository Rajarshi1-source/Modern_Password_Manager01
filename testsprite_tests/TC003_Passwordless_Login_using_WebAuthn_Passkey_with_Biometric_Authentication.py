import asyncio
from playwright import async_api
from playwright.async_api import expect

async def run_test():
    pw = None
    browser = None
    context = None
    
    try:
        # Start a Playwright session in asynchronous mode
        pw = await async_api.async_playwright().start()
        
        # Launch a Chromium browser in headless mode with custom arguments
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--window-size=1280,720",         # Set the browser window size
                "--disable-dev-shm-usage",        # Avoid using /dev/shm which can cause issues in containers
                "--ipc=host",                     # Use host-level IPC for better stability
                "--single-process"                # Run the browser in a single process mode
            ],
        )
        
        # Create a new browser context (like an incognito window)
        context = await browser.new_context()
        context.set_default_timeout(5000)
        
        # Open a new page in the browser context
        page = await context.new_page()
        
        # Navigate to your target URL and wait until the network request is committed
        await page.goto("http://localhost:5173", wait_until="commit", timeout=10000)
        
        # Wait for the main page to reach DOMContentLoaded state (optional for stability)
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=3000)
        except async_api.Error:
            pass
        
        # Iterate through all iframes and wait for them to load as well
        for frame in page.frames:
            try:
                await frame.wait_for_load_state("domcontentloaded", timeout=3000)
            except async_api.Error:
                pass
        
        # Interact with the page elements to simulate user flow
        # -> Click the 'Login with a Passkey' button to choose passwordless WebAuthn login option.
        frame = context.pages[-1]
        # Click the 'Login with a Passkey' button to choose passwordless WebAuthn login option.
        elem = frame.locator('xpath=html/body/div/div/div[2]/header/div[3]/div[3]/form/div[4]/button').nth(0)
        await page.wait_for_timeout(3000); await elem.click(timeout=5000)
        

        # -> Trigger the passkey authentication prompt by clicking the 'Login with a Passkey' button again or interacting with the prompt if it appears.
        frame = context.pages[-1]
        # Trigger passkey authentication prompt by clicking 'Login with a Passkey' button.
        elem = frame.locator('xpath=html/body/div/div/div[2]/header/div[3]/div[3]/form/div[4]/button').nth(0)
        await page.wait_for_timeout(3000); await elem.click(timeout=5000)
        

        # --> Assertions to verify final state
        frame = context.pages[-1]
        try:
            await expect(frame.locator('text=Passkey Authentication Successful')).to_be_visible(timeout=1000)
        except AssertionError:
            raise AssertionError('Test failed: Passwordless login using registered WebAuthn passkey including biometric factor validation did not succeed as expected.')
        await asyncio.sleep(5)
    
    finally:
        if context:
            await context.close()
        if browser:
            await browser.close()
        if pw:
            await pw.stop()
            
asyncio.run(run_test())
    