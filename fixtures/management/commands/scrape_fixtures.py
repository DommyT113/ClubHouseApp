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

# --- (All helper functions are the same as before) ---
def get_target_saturday():
    today = datetime.today()
    first_fixture_date = datetime(2025, 9, 20)
    weekday = today.weekday()
    if weekday <= 4:
        days_until_saturday = 5 - weekday
        target_saturday = today + timedelta(days=days_until_saturday)
    else:
        days_since_saturday = weekday - 5
        target_saturday = today - timedelta(days=days_since_saturday)
    return max(target_saturday, first_fixture_date)

def has_fixtures_on_day(date_obj, service):
    date_str = date_obj.strftime('%Y-%m-%d')
    url = f"https://southeast.englandhockey.co.uk/clubs/burnt-ash--bexley--hc?match-day={date_str}"
    print(f"Checking for fixtures on {date_str}...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--log-level=3")
    driver = webdriver.Chrome(service=service, options=options)
    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "c-match-detail-card__container")))
        return True
    except TimeoutException:
        print(f"No fixtures found for {date_str}.")
        return False
    finally:
        driver.quit()

def normalize_team_name(name):
    return name.strip()

def ordinal(n):
    if not isinstance(n, int): return n
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return str(n) + suffix

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
    "South East Open - Men's Division 9 Invicta": "https://southeast.englandhockey.co.uk/competitions/2025-2026-4601609-adult-south-east-open---mens-group-4602900-south-east-open---mens-division-9-invicta/table"
}

def get_league_positions(division_name, service):
    league_positions = {}
    league_url = DIVISION_URLS.get(division_name)
    if not league_url: return league_positions
    options = webdriver.ChromeOptions()
    options.add_argument("--headless"); options.add_argument("--log-level=3")
    driver = webdriver.Chrome(service=service, options=options)
    try:
        driver.get(league_url)
        WebDriverWait(driver, 20).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".c-table-container tbody tr")))
        table_rows = driver.find_elements(By.CSS_SELECTOR, ".c-table-container tbody tr")
        for row in table_rows:
            position = row.find_element(By.CSS_SELECTOR, "td:nth-child(1)").text.strip()
            team_name = row.find_element(By.CSS_SELECTOR, "td:nth-child(2)").text.strip()
            league_positions[normalize_team_name(team_name)] = ordinal(int(position))
    except (TimeoutException, WebDriverException, ValueError) as e:
        print(f"Could not fetch league table for {division_name}: {e}")
    finally:
        driver.quit()
    return league_positions

class Command(BaseCommand):
    help = 'Scrapes the club page for all weekend fixtures (Sat & Sun).'
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🚀 Starting the weekend fixture scraper..."))
        start_time = time.time()
        service = Service(ChromeDriverManager().install())
        target_saturday = get_target_saturday()
        target_sunday = target_saturday + timedelta(days=1)
        weekend_dates = [target_saturday, target_sunday]
        all_weekend_fixtures = []
        for day in weekend_dates:
            if not has_fixtures_on_day(day, service): continue
            date_str = day.strftime('%Y-%m-%d')
            fixtures_url = f"https://southeast.englandhockey.co.uk/clubs/burnt-ash--bexley--hc?match-day={date_str}"
            self.stdout.write(f"Scraping fixtures from: {fixtures_url}")
            options = webdriver.ChromeOptions()
            options.add_argument("--headless"); options.add_argument("--log-level=3")
            driver = webdriver.Chrome(service=service, options=options)
            try:
                driver.get(fixtures_url)
                WebDriverWait(driver, 20).until(EC.presence_of_all_elements_located((By.CLASS_NAME, "c-match-detail-card__container")))
                fixture_containers = driver.find_elements(By.CLASS_NAME, "c-match-detail-card__container")
                previous_division = 'Unknown'
                for container in fixture_containers:
                    try:
                        try:
                            division_element = container.find_element(By.XPATH, "./preceding-sibling::div[1]/h2/a")
                            division = division_element.text.strip()
                            previous_division = division
                        except NoSuchElementException:
                            division = previous_division
                        fixture_body = container.find_element(By.CLASS_NAME, "c-fixture__body")
                        home_team_name = fixture_body.find_element(By.CSS_SELECTOR, '.c-fixture__badge-before .c-badge__label').text.strip()
                        home_badge = fixture_body.find_element(By.CSS_SELECTOR, '.c-fixture__badge-before .c-badge__image').get_attribute('src')
                        away_team_name = fixture_body.find_element(By.CSS_SELECTOR, '.c-fixture__badge-after .c-badge__label').text.strip()
                        away_badge = fixture_body.find_element(By.CSS_SELECTOR, '.c-fixture__badge-after .c-badge__image').get_attribute('src')
                        scores = fixture_body.find_elements(By.CSS_SELECTOR, '.c-score__item')
                        home_score = scores[0].text.strip() if scores else ''
                        away_score = scores[1].text.strip() if len(scores) > 1 else ''
                        try:
                            decision = container.find_element(By.CLASS_NAME, 'c-fixture__status').text.strip().title()
                        except NoSuchElementException:
                            decision = 'Scheduled' if not home_score else 'Played'
                        all_weekend_fixtures.append({
                            "match_date": day.date(), "division": division, "home_team": home_team_name, "home_team_badge_url": home_badge,
                            "home_score": home_score, "away_team": away_team_name, "away_team_badge_url": away_badge,
                            "away_score": away_score, "decision": decision
                        })
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error processing a fixture container: {e}"))
            finally:
                driver.quit()
        if not all_weekend_fixtures:
            self.stdout.write(self.style.WARNING("No fixtures found for the entire weekend. Exiting."))
            return
        self.stdout.write("Clearing old fixtures for the upcoming weekend...")
        Fixture.objects.filter(match_date__in=[d.date() for d in weekend_dates]).delete()
        self.stdout.write(f"Found {len(all_weekend_fixtures)} total fixtures. Processing and saving...")
        for fixture_data in all_weekend_fixtures:
            division, _ = Division.objects.get_or_create(name=fixture_data['division'])
            home_team, _ = Team.objects.update_or_create(name=normalize_team_name(fixture_data['home_team']), defaults={'badge_url': fixture_data['home_team_badge_url']})
            away_team, _ = Team.objects.update_or_create(name=normalize_team_name(fixture_data['away_team']), defaults={'badge_url': fixture_data['away_team_badge_url']})
            home_pos, away_pos = 'N/A', 'N/A'
            if fixture_data['division'] in DIVISION_URLS:
                positions = get_league_positions(fixture_data['division'], service)
                home_pos = positions.get(normalize_team_name(fixture_data['home_team']), 'N/A')
                away_pos = positions.get(normalize_team_name(fixture_data['away_team']), 'N/A')
            h_score = int(fixture_data['home_score']) if fixture_data['home_score'].isdigit() else None
            a_score = int(fixture_data['away_score']) if fixture_data['away_score'].isdigit() else None
            Fixture.objects.create(
                home_team=home_team, away_team=away_team, match_date=fixture_data['match_date'], division=division,
                home_score=h_score, away_score=a_score, home_league_pos=home_pos, away_league_pos=away_pos,
                decision=fixture_data['decision'],
            )
            self.stdout.write(f"  - CREATED: {fixture_data['home_team']} vs {fixture_data['away_team']}")
        end_time = time.time()
        self.stdout.write(self.style.SUCCESS(f"✅ Scrape complete! Time taken: {end_time - start_time:.2f} seconds."))