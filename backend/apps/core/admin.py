from django.contrib import admin

from .models import (
    CaseLibraryDocument,
    CommonIssueReport,
    ConversationRecord,
    MentorshipApplication,
    MentorshipRelation,
    MessageNotification,
    Plan,
    PromptSceneConfig,
    ReviewRecord,
    ScoringRubric,
    User,
)

admin.site.register(User)
admin.site.register(Plan)
admin.site.register(ReviewRecord)
admin.site.register(MentorshipApplication)
admin.site.register(MentorshipRelation)
admin.site.register(MessageNotification)
admin.site.register(CommonIssueReport)
admin.site.register(CaseLibraryDocument)
admin.site.register(PromptSceneConfig)
admin.site.register(ScoringRubric)

