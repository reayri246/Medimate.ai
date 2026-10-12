from django.contrib import admin

from .models import ActiveIngredient, Medicine, MedicineIngredient


@admin.register(ActiveIngredient)
class ActiveIngredientAdmin(admin.ModelAdmin):
    list_display = ('name', 'standard_name', 'information_verified', 'last_verified')
    list_filter = ('information_verified',)
    search_fields = ('name', 'standard_name', 'aliases')


class MedicineIngredientInline(admin.TabularInline):
    model = MedicineIngredient
    extra = 1
    autocomplete_fields = ('ingredient',)


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'active_ingredient',
        'category',
        'is_non_prescription',
        'safety_data_verified',
    )
    list_filter = ('category', 'is_non_prescription', 'safety_data_verified')
    search_fields = ('name', 'active_ingredient', 'ingredients__name', 'ingredients__standard_name')
    prepopulated_fields = {'slug': ('name',)}
    inlines = (MedicineIngredientInline,)
    fieldsets = (
        ('Medicine details', {
            'fields': ('name', 'active_ingredient', 'dosage_form', 'strength', 'category', 'slug'),
        }),
        ('Source and verification', {
            'fields': (
                'is_non_prescription',
                'safety_data_verified',
                'source_name',
                'source_url',
                'last_verified',
            ),
            'description': (
                'Only mark verified after the displayed composition and safety information have been '
                'checked against the cited source.'
            ),
        }),
        ('Safety and reference information', {
            'fields': ('description', 'warnings', 'side_effects', 'interactions', 'contraindications'),
        }),
    )
