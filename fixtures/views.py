import json
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Fixture, Player, Goal


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


def tv_display_view(request):
    all_fixtures = Fixture.objects.order_by('match_date', 'division__name').all()
    flat_fixture_list = list(all_fixtures)
    context = {'flat_fixture_list': flat_fixture_list}
    return render(request, 'fixtures/tv_display.html', context)


@login_required
@permission_required('fixtures.change_fixture', raise_exception=True)
def update_scorers(request, fixture_id):
    fixture = get_object_or_404(Fixture, id=fixture_id)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

        player_id = data.get('player_id')
        quantity = data.get('quantity')

        if player_id is None or quantity is None:
            return JsonResponse({'status': 'error', 'message': 'Invalid data'}, status=400)

        player = get_object_or_404(Player, id=player_id)

        if int(quantity) > 0:
            Goal.objects.update_or_create(
                fixture=fixture, player=player, defaults={'quantity': int(quantity)}
            )
        else:
            Goal.objects.filter(fixture=fixture, player=player).delete()

        goals = fixture.goals.all().order_by('player__full_name')
        fixture.scorers_text = ", ".join([f"{g.player.full_name} ({g.quantity})" for g in goals if g.quantity > 0])
        fixture.save()

        return JsonResponse({'status': 'success'})

    all_players = Player.objects.all()
    existing_goals = {str(goal.player_id): goal.quantity for goal in fixture.goals.all()}

    context = {
        'fixture': fixture,
        'all_players_json': json.dumps(list(all_players.values('id', 'full_name', 'gender'))),
        'existing_goals_json': json.dumps(existing_goals),
    }
    return render(request, 'fixtures/update_scorers.html', context)


@login_required
@permission_required('fixtures.change_fixture', raise_exception=True)
@require_POST
def add_player(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    full_name = data.get('full_name', '').strip()
    gender = data.get('gender')

    if not full_name or not gender:
        return JsonResponse({'status': 'error', 'message': 'Full name and gender are required.'}, status=400)

    if Player.objects.filter(full_name__iexact=full_name).exists():
        return JsonResponse({'status': 'error', 'message': 'A player with this name already exists.'}, status=400)

    player = Player.objects.create(full_name=full_name, gender=gender)
    return JsonResponse(
        {'status': 'success', 'player': {'id': player.id, 'full_name': player.full_name, 'gender': player.gender}})