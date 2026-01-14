from django.contrib import admin
from .models import (
    AdversarialBattle,
    AttackVector,
    DefenseRecommendation,
    AggregatedBreachPattern,
    UserDefenseProfile
)


@admin.register(AdversarialBattle)
class AdversarialBattleAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'outcome', 'attack_score', 'defense_score', 'created_at']
    list_filter = ['outcome', 'created_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['password_hash', 'created_at', 'completed_at']
    date_hierarchy = 'created_at'


@admin.register(AttackVector)
class AttackVectorAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'severity', 'base_success_rate', 'is_active']
    list_filter = ['category', 'severity', 'is_active']
    search_fields = ['name', 'description']
    list_editable = ['is_active']


@admin.register(DefenseRecommendation)
class DefenseRecommendationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'priority', 'status', 'created_at']
    list_filter = ['priority', 'status', 'created_at']
    search_fields = ['title', 'user__username']
    filter_horizontal = ['attack_vectors_addressed']


@admin.register(AggregatedBreachPattern)
class AggregatedBreachPatternAdmin(admin.ModelAdmin):
    list_display = ['pattern_type', 'pattern_signature', 'occurrence_count', 'is_trending']
    list_filter = ['pattern_type', 'is_trending']
    search_fields = ['pattern_signature']
    readonly_fields = ['first_observed', 'last_observed']


@admin.register(UserDefenseProfile)
class UserDefenseProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'overall_defense_score', 'total_battles', 'battles_won', 'battles_lost']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at', 'last_battle_at']
