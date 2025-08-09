from django.db import models

class Division(models.Model):
    name = models.CharField(max_length=200, unique=True)
    league_table_url = models.URLField(max_length=500, blank=True, null=True)
    class Meta:
        ordering = ['name']
    def __str__(self):
        return self.name

class Team(models.Model):
    name = models.CharField(max_length=200, unique=True)
    badge_url = models.URLField(max_length=500, blank=True, null=True)
    division = models.ForeignKey(Division, on_delete=models.SET_NULL, null=True, blank=True, related_name='teams')
    class Meta:
        ordering = ['name']
    def __str__(self):
        return self.name

class Fixture(models.Model):
    class Decision(models.TextChoices):
        SCHEDULED = 'Scheduled'
        PLAYED = 'Played'
        WALKOVER = 'Walkover'
        POSTPONED = 'Postponed'
        BYE = 'Bye'
    division = models.ForeignKey(Division, on_delete=models.CASCADE, related_name='fixtures')
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='home_fixtures')
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='away_fixtures')
    match_date = models.DateField()
    home_score = models.IntegerField(null=True, blank=True)
    away_score = models.IntegerField(null=True, blank=True)
    home_league_pos = models.CharField(max_length=10, blank=True, null=True)
    away_league_pos = models.CharField(max_length=10, blank=True, null=True)
    decision = models.CharField(max_length=20, choices=Decision.choices, default=Decision.SCHEDULED)
    scorers_text = models.TextField(blank=True, null=True)
    class Meta:
        ordering = ['match_date', 'division__name']
        unique_together = ('home_team', 'away_team', 'match_date')
    def __str__(self):
        return f"{self.home_team} vs {self.away_team} on {self.match_date}"

class Player(models.Model):
    class Gender(models.TextChoices):
        MALE = 'Male'
        FEMALE = 'Female'
    full_name = models.CharField(max_length=200, unique=True)
    gender = models.CharField(max_length=10, choices=Gender.choices)
    class Meta:
        ordering = ['full_name']
    def __str__(self):
        return self.full_name

class Goal(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='goals')
    fixture = models.ForeignKey(Fixture, on_delete=models.CASCADE, related_name='goals')
    quantity = models.PositiveIntegerField(default=1)
    class Meta:
        unique_together = ('player', 'fixture')
    def __str__(self):
        return f"{self.player.full_name} ({self.quantity}) in {self.fixture}"