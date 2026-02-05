using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;

namespace EpsteinDashboard.Application.Services;

public class TimelineService
{
    private readonly IEventRepository _eventRepository;

    public TimelineService(IEventRepository eventRepository)
    {
        _eventRepository = eventRepository;
    }

    public async Task<PagedResult<TimelineEntry>> GetTimelineAsync(
        int page = 0, int pageSize = 100,
        string? eventType = null, string? dateFrom = null, string? dateTo = null,
        CancellationToken cancellationToken = default)
    {
        var eventsResult = await _eventRepository.GetFilteredAsync(
            page, pageSize, eventType, dateFrom, dateTo,
            sortBy: "EventDate", sortDirection: "asc",
            cancellationToken: cancellationToken);

        var entries = new List<TimelineEntry>();

        foreach (var evt in eventsResult.Items)
        {
            var fullEvent = await _eventRepository.GetWithParticipantsAsync(evt.EventId, cancellationToken);
            var participantNames = fullEvent?.Participants
                .Where(p => p.Person != null)
                .Select(p => p.Person!.FullName)
                .ToList() ?? new List<string>();

            entries.Add(new TimelineEntry
            {
                EventId = evt.EventId,
                Title = evt.Title,
                EventDate = evt.EventDate,
                EndDate = evt.EndDate,
                EventType = evt.EventType,
                Location = evt.Location?.LocationName,
                ParticipantNames = participantNames
            });
        }

        return new PagedResult<TimelineEntry>
        {
            Items = entries,
            TotalCount = eventsResult.TotalCount,
            Page = page,
            PageSize = pageSize
        };
    }
}
