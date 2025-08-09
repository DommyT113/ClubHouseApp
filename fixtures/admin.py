from django.contrib import admin
from .models import Division, Team, Fixture, Player, Goal

admin.site.register(Division)
admin.site.register(Team)
admin.site.register(Fixture)
admin.site.register(Player)
admin.site.register(Goal)