import time
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException

from fixtures.models import Division, Team, Fixture


# -----------------------------
# Helpers & configuration
# -----------------------------

def make_driver(service: Service) -> webdriver.Chrome:
    """Create a fast, quiet, reusable headless Chrome driver."""
    options = webdriver.ChromeOptions()
    # Headless mode (new headless is faster)
    options.add_argument("--headless=new")
    # Quieter logs
    options.add_argument("--log-level=3")
    options.add_argument("--disable-logging")
    # Common flags for CI/servers
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    # Load pages without waiting for every subresource
    options.page_load_strategy = "eager"
    return webdriver.Chrome(service=service, options=options)


def get_target_saturday():
    """Find the Saturday to scrape (first Saturday on/after season start, or previous if today is Sun-Mon?).
    Logic: If Mon–Fri, next Sat; if Sat/Sun, use Sat of this weekend; not earlier than first_fixture_date."""
    today = datetime.today()
    first_fixture_date = datetime(2025, 9, 20)
    weekday = today.weekday()  # Mon=0 ... Sun=6
    if weekday <= 4:
        days_until_saturday = 5 - weekday
        target_saturday = today + timedelta(days=days_until_saturday)
    else:
        days_since_saturday = weekday - 5
        target_saturday = today - timedelta(days=days_since_saturday)
    return max(target_saturday.replace(hour=0, minute=0, second=0, microsecond=0), first_fixture_date)


def normalize_team_name(name: str) -> str:
    return name.strip()


def ordinal(n):
    if not isinstance(n, int):
        return n
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"


DIVISION_URLS = {
    "South East Women's Division 1 East": "https://southeast.englandhockey.co.uk/competitions/south-east-womens-division-1-east/table",
    "South East Open - Men's Division 1 East": "https://southeast.englandhockey.co.uk/competitions/south-east-open---mens-division-1-east/table",
    "South East Women's Division 1 Invicta": "https://southeast.englandhockey.co.uk/competitions/south-east-womens-division-1-invicta/table",
    "South East Open - Men's Division 2 Invicta": "https://southeast.englandhockey.co.uk/competitions/south-east-open---mens-division-2-invicta/table",
    "South East Women's Division 3 Invicta": "https://southeast.englandhockey.co.uk/competitions/south-east-womens-division-3-invicta/table",
    "South East Open - Men's Division 4 Invicta": "https://southeast.englandhockey.co.uk/competitions/south-east-open---mens-division-4-invicta/table",
    "South East Open - Men's Division 5 Invicta": "https://southeast.englandhockey.co.uk/competitions/south-east-open---mens-division-5-invicta/table",
    "South East Women's Division 5 Invicta": "https://southeast.englandhockey.co.uk/competitions/south-east-womens-division-5-invicta/table",
    "South East Open - Men's Division 6 Invicta": "https://southeast.englandhockey.co.uk/competitions/2025-2026-4601609-adult-south-east-open---mens-group-4602608-south-east-open---mens-division-6-invicta/table",
    "South East Women's Division 6 Invicta": "https://southeast.englandhockey.co.uk/competitions/south-east-womens-division-6-invicta/table",
    "South East Open - Men's Division 8 Invicta": "https://southeast.englandhockey.co.uk/competitions/2025-2026-4601609-adult-south-east-open---mens-group-4602806-south-east-open---mens-division-8-invicta/table",
    "South East Women's Division 7 Invicta": "https://southeast.englandhockey.co.uk/competitions/south-east-womens-division-7-invicta/table",
    "South East Open - Men's Division 9 Invicta": "https://southeast.englandhockey.co.uk/competitions/2025-2026-4601609-adult-south-east-open---mens-group-4602900-south-east-open---mens-division-9-invicta/table",
}


def get_league_positions_with_driver(driver: webdriver.Chrome, division_name: str) -> dict:
    """Scrape a division table into {team_name: position_str} using an already-open driver."""
    league_positions = {}
    league_url = DIVISION_URLS.get(division_name)
    if not league_url:
        return league_positions
    try:
        driver.get(league_url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".c-table-container tbody tr"))
        )
        rows = driver.find_elements(By.CSS_SELECTOR, ".c-table-container tbody tr")
        for row in rows:
            try:
                pos_txt = row.find_element(By.CSS_SELECTOR, "td:nth-child(1)").text.strip()
                team_txt = row.find_element(By.CSS_SELECTOR, "td:nth-child(2)").text.strip()
                league_positions[normalize_team_name(team_txt)] = ordinal(int(pos_txt))
            except Exception:
                # Skip any malformed row without killing the scrape
                continue
    except (TimeoutException, WebDriverException) as e:
        print(f"Could not fetch league table for {division_name}: {e}")
    return league_positions


def preload_league_positions(service: Service) -> dict:
    """Load ALL divisions once and cache."""
    cache = {}
    tables_driver = make_driver(service)
    try:
        for division_name in DIVISION_URLS:
            cache[division_name] = get_league_positions_with_driver(tables_driver, division_name)
    finally:
        tables_driver.quit()
    return cache


def scrape_fixtures_for_day(driver: webdriver.Chrome, date_obj: datetime) -> list[dict]:
    """Return a list of fixture dicts for a given date. Uses a single, provided driver."""
    date_str = date_obj.strftime('%Y-%m-%d')
    url = f"https://southeast.englandhockey.co.uk/clubs/burnt-ash--bexley--hc?match-day={date_str}"

    fixtures_for_day = []

    driver.get(url)
    try:
        # If there are no fixtures, this will timeout quickly
        WebDriverWait(driver, 6).until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "c-match-detail-card__container"))
        )
    except TimeoutException:
        # No fixtures on this date
        return fixtures_for_day

    fixture_containers = driver.find_elements(By.CLASS_NAME, "c-match-detail-card__container")
    previous_division = 'Unknown'

    for container in fixture_containers:
        try:
            # Try to read the division from the nearest preceding block header
            try:
                division_element = container.find_element(By.XPATH, "./preceding-sibling::div[1]/h2/a")
                division = division_element.text.strip()
                previous_division = division
            except NoSuchElementException:
                division = previous_division

            fixture_body = container.find_element(By.CLASS_NAME, "c-fixture__body")

            home_team_name = fixture_body.find_element(
                By.CSS_SELECTOR, '.c-fixture__badge-before .c-badge__label'
            ).text.strip()
            home_badge = fixture_body.find_element(
                By.CSS_SELECTOR, '.c-fixture__badge-before .c-badge__image'
            ).get_attribute('src')

            away_team_name = fixture_body.find_element(
                By.CSS_SELECTOR, '.c-fixture__badge-after .c-badge__label'
            ).text.strip()
            away_badge = fixture_body.find_element(
                By.CSS_SELECTOR, '.c-fixture__badge-after .c-badge__image'
            ).get_attribute('src')

            scores = fixture_body.find_elements(By.CSS_SELECTOR, '.c-score__item')
            home_score = scores[0].text.strip() if len(scores) > 0 else ''
            away_score = scores[1].text.strip() if len(scores) > 1 else ''

            try:
                decision = container.find_element(By.CLASS_NAME, 'c-fixture__status').text.strip().title()
            except NoSuchElementException:
                decision = 'Scheduled' if not home_score else 'Played'

            fixtures_for_day.append({
                "match_date": date_obj.date(),
                "division": division,
                "home_team": home_team_name,
                "home_team_badge_url": home_badge,
                "home_score": home_score,
                "away_team": away_team_name,
                "away_team_badge_url": away_badge,
                "away_score": away_score,
                "decision": decision,
            })
        except Exception as e:
            # Keep going even if a single card fails
            print(f"Error processing a fixture container: {e}")
            continue

    return fixtures_for_day


# -----------------------------
# Django management command
# -----------------------------

class Command(BaseCommand):
    help = 'Scrapes the club page for all weekend fixtures (Sat & Sun) and stores them with cached league positions.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🚀 Starting the weekend fixture scraper..."))
        start_time = time.time()

        # Single Service and drivers reused to avoid repeated Chrome launches
        service = Service(ChromeDriverManager().install())

        target_saturday = get_target_saturday()
        target_sunday = target_saturday + timedelta(days=1)
        weekend_dates = [target_saturday, target_sunday]

        # 1) Scrape fixtures with ONE driver reused
        fixtures_driver = make_driver(service)
        try:
            all_weekend_fixtures = []
            for day in weekend_dates:
                self.stdout.write(f"Scraping fixtures for {day.strftime('%Y-%m-%d')} ...")
                day_fixtures = scrape_fixtures_for_day(fixtures_driver, day)
                if not day_fixtures:
                    self.stdout.write(self.style.WARNING(f"  - No fixtures found for {day.strftime('%Y-%m-%d')}"))
                else:
                    self.stdout.write(f"  - Found {len(day_fixtures)} fixtures")
                    all_weekend_fixtures.extend(day_fixtures)
        finally:
            fixtures_driver.quit()

        if not all_weekend_fixtures:
            self.stdout.write(self.style.WARNING("No fixtures found for the entire weekend. Exiting."))
            return

        # 2) Preload ALL league tables ONCE (second driver)
        self.stdout.write("Preloading league tables once...")
        positions_cache = preload_league_positions(service)

        # 3) Replace weekend fixtures for those dates
        self.stdout.write("Clearing old fixtures for the upcoming weekend...")
        Fixture.objects.filter(match_date__in=[d.date() for d in weekend_dates]).delete()

        # 4) Save fixtures with cached positions
        self.stdout.write(f"Saving {len(all_weekend_fixtures)} fixtures...")
        created_count = 0

        for fx in all_weekend_fixtures:
            division_obj, _ = Division.objects.get_or_create(name=fx['division'])

            home_team, _ = Team.objects.update_or_create(
                name=normalize_team_name(fx['home_team']),
                defaults={'badge_url': fx['home_team_badge_url']}
            )
            away_team, _ = Team.objects.update_or_create(
                name=normalize_team_name(fx['away_team']),
                defaults={'badge_url': fx['away_team_badge_url']}
            )

            positions = positions_cache.get(fx['division'], {})
            home_pos = positions.get(normalize_team_name(fx['home_team']), 'N/A')
            away_pos = positions.get(normalize_team_name(fx['away_team']), 'N/A')

            h_score = int(fx['home_score']) if fx['home_score'].isdigit() else None
            a_score = int(fx['away_score']) if fx['away_score'].isdigit() else None

            Fixture.objects.create(
                home_team=home_team,
                away_team=away_team,
                match_date=fx['match_date'],
                division=division_obj,
                home_score=h_score,
                away_score=a_score,
                home_league_pos=home_pos,
                away_league_pos=away_pos,
                decision=fx['decision'],
            )
            created_count += 1
            self.stdout.write(f"  - CREATED: {fx['home_team']} vs {fx['away_team']}")

        elapsed = time.time() - start_time
        self.stdout.write(self.style.SUCCESS(f"✅ Scrape complete! Created {created_count} fixtures in {elapsed:.2f}s."))
