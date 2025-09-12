from django.contrib import admin
from .models import Division, Team, Fixture, Player, Goal

# This is a class that defines how to show Goal entries inside another model's admin page
class GoalInline(admin.TabularInline):
    model = Goal
    # Provides an autocomplete search box for players instead of a huge dropdown
    autocomplete_fields = ['player']
    # How many extra empty rows to show
    extra = 1

@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    # This enables the search box for players
    search_fields = ['full_name']
    list_display = ('full_name', 'gender')
    list_filter = ('gender',)

@admin.register(Fixture)
class FixtureAdmin(admin.ModelAdmin):
    list_display = ('match_date', 'home_team', 'away_team', 'division')
    list_filter = ('match_date', 'division')
    # This is the key part: it adds the Goal entry form to the Fixture page
    inlines = [GoalInline]

# We can keep these simple registrations for basic management
admin.site.register(Division)
admin.site.register(Team)
admin.site.register(Goal) # This allows managing goals separately if needed