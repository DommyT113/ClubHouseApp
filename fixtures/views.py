import json
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Fixture, Player, Goal


# This function is correct and needs no changes
def fixture_list(request):
    all_fixtures = Fixture.objects.order_by('match_date', 'division__name').all()
    grouped_fixtures = {}
    for fixture in all_fixtures:
        division_name = fixture.division.name
        if division_name not in grouped_fixtures:
            grouped_fixtures[division_name] = []
        grouped_fixtures[division_name].append(fixture)
    context = {'grouped_fixtures': grouped_fixtures}
    return render(request, 'fixtures/fixture_list.html', context)


# This function is correct and needs no changes
def tv_display_view(request):
    all_fixtures = Fixture.objects.order_by('match_date', 'division__name').all()
    flat_fixture_list = list(all_fixtures)
    context = {'flat_fixture_list': flat_fixture_list}
    return render(request, 'fixtures/tv_display.html', context)


# --- NEW SCORER VIEWS ---

@login_required
@permission_required('fixtures.change_fixture', raise_exception=True)
def update_scorers(request, fixture_id):
    fixture = get_object_or_404(Fixture, id=fixture_id)
    all_players = list(Player.objects.values('id', 'full_name'))  # Keep it simple for JSON

    # Pass the existing goals in a clear list format for the new JS
    existing_goals = list(Goal.objects.filter(fixture=fixture).values('player_id', 'quantity'))

    context = {
        'fixture': fixture,
        # The |safe filter is the correct choice for this robust JS script
        'all_players': all_players,
        'existing_goals': existing_goals,
    }
    return render(request, 'fixtures/update_scorers.html', context)


@login_required
@permission_required('fixtures.change_fixture', raise_exception=True)
@require_POST
def add_or_update_goal(request, fixture_id):
    try:
        data = json.loads(request.body)
        player_id = data.get('player_id')
        quantity = int(data.get('quantity', 0))
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'status': 'error', 'message': 'Invalid data'}, status=400)

    fixture = get_object_or_404(Fixture, id=fixture_id)
    player = get_object_or_404(Player, id=player_id)

    if quantity > 0:
        Goal.objects.update_or_create(fixture=fixture, player=player, defaults={'quantity': quantity})
    else:
        Goal.objects.filter(fixture=fixture, player=player).delete()

    # Update the simple text field for other displays
    goals = fixture.goals.select_related('player').order_by('player__full_name')
    fixture.scorers_text = ", ".join([f"{g.player.full_name} ({g.quantity})" for g in goals])
    fixture.save()

    return JsonResponse({'status': 'success'})


@login_required
@permission_required('fixtures.change_fixture', raise_exception=True)
@require_POST
def add_player(request):
    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({'status': 'error', 'message': 'Invalid data'}, status=400)

    full_name = data.get('full_name', '').strip()
    gender = data.get('gender')
    if not full_name or not gender:
        return JsonResponse({'status': 'error', 'message': 'All fields are required'}, status=400)

    if Player.objects.filter(full_name__iexact=full_name).exists():
        return JsonResponse({'status': 'error', 'message': 'Player with this name already exists'}, status=400)

    player = Player.objects.create(full_name=full_name, gender=gender)
    return JsonResponse({'status': 'success', 'player': {'id': player.id, 'full_name': player.full_name}})