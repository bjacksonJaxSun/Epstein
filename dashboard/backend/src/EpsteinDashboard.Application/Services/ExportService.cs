using System.Text;
using System.Text.Json;
using EpsteinDashboard.Core.Interfaces;

namespace EpsteinDashboard.Application.Services;

public class ExportService : IExportService
{
    private readonly IDocumentRepository _documentRepository;
    private readonly IPersonRepository _personRepository;
    private readonly IOrganizationRepository _organizationRepository;
    private readonly ILocationRepository _locationRepository;
    private readonly IEventRepository _eventRepository;
    private readonly IRelationshipRepository _relationshipRepository;

    public ExportService(
        IDocumentRepository documentRepository,
        IPersonRepository personRepository,
        IOrganizationRepository organizationRepository,
        ILocationRepository locationRepository,
        IEventRepository eventRepository,
        IRelationshipRepository relationshipRepository)
    {
        _documentRepository = documentRepository;
        _personRepository = personRepository;
        _organizationRepository = organizationRepository;
        _locationRepository = locationRepository;
        _eventRepository = eventRepository;
        _relationshipRepository = relationshipRepository;
    }

    public async Task<byte[]> ExportToCsvAsync(string entityType, Dictionary<string, string>? filters = null, CancellationToken cancellationToken = default)
    {
        var sb = new StringBuilder();

        switch (entityType.ToLowerInvariant())
        {
            case "documents":
                var docs = await _documentRepository.GetAllAsync(cancellationToken);
                sb.AppendLine("DocumentId,EftaNumber,DocumentType,DocumentDate,DocumentTitle,Author,Subject,PageCount,ExtractionStatus");
                foreach (var d in docs)
                    sb.AppendLine($"{d.DocumentId},{CsvEscape(d.EftaNumber)},{CsvEscape(d.DocumentType)},{CsvEscape(d.DocumentDate)},{CsvEscape(d.DocumentTitle)},{CsvEscape(d.Author)},{CsvEscape(d.Subject)},{d.PageCount},{CsvEscape(d.ExtractionStatus)}");
                break;

            case "people":
                var people = await _personRepository.GetAllAsync(cancellationToken);
                sb.AppendLine("PersonId,FullName,PrimaryRole,Occupation,Nationality,ConfidenceLevel");
                foreach (var p in people)
                    sb.AppendLine($"{p.PersonId},{CsvEscape(p.FullName)},{CsvEscape(p.PrimaryRole)},{CsvEscape(p.Occupation)},{CsvEscape(p.Nationality)},{CsvEscape(p.ConfidenceLevel)}");
                break;

            case "organizations":
                var orgs = await _organizationRepository.GetAllAsync(cancellationToken);
                sb.AppendLine("OrganizationId,OrganizationName,OrganizationType,HeadquartersLocation");
                foreach (var o in orgs)
                    sb.AppendLine($"{o.OrganizationId},{CsvEscape(o.OrganizationName)},{CsvEscape(o.OrganizationType)},{CsvEscape(o.HeadquartersLocation)}");
                break;

            case "locations":
                var locs = await _locationRepository.GetAllAsync(cancellationToken);
                sb.AppendLine("LocationId,LocationName,LocationType,City,StateProvince,Country,Latitude,Longitude");
                foreach (var l in locs)
                    sb.AppendLine($"{l.LocationId},{CsvEscape(l.LocationName)},{CsvEscape(l.LocationType)},{CsvEscape(l.City)},{CsvEscape(l.StateProvince)},{CsvEscape(l.Country)},{l.Latitude},{l.Longitude}");
                break;

            case "events":
                var events = await _eventRepository.GetAllAsync(cancellationToken);
                sb.AppendLine("EventId,EventType,Title,EventDate,ConfidenceLevel,VerificationStatus");
                foreach (var e in events)
                    sb.AppendLine($"{e.EventId},{CsvEscape(e.EventType)},{CsvEscape(e.Title)},{CsvEscape(e.EventDate)},{CsvEscape(e.ConfidenceLevel)},{CsvEscape(e.VerificationStatus)}");
                break;

            case "relationships":
                var rels = await _relationshipRepository.GetAllAsync(cancellationToken);
                sb.AppendLine("RelationshipId,Person1Id,Person2Id,RelationshipType,StartDate,EndDate,IsCurrent,ConfidenceLevel");
                foreach (var r in rels)
                    sb.AppendLine($"{r.RelationshipId},{r.Person1Id},{r.Person2Id},{CsvEscape(r.RelationshipType)},{CsvEscape(r.StartDate)},{CsvEscape(r.EndDate)},{r.IsCurrent},{CsvEscape(r.ConfidenceLevel)}");
                break;

            default:
                throw new ArgumentException($"Unknown entity type: {entityType}");
        }

        return Encoding.UTF8.GetBytes(sb.ToString());
    }

    public async Task<byte[]> ExportToJsonAsync(string entityType, Dictionary<string, string>? filters = null, CancellationToken cancellationToken = default)
    {
        object data = entityType.ToLowerInvariant() switch
        {
            "documents" => await _documentRepository.GetAllAsync(cancellationToken),
            "people" => await _personRepository.GetAllAsync(cancellationToken),
            "organizations" => await _organizationRepository.GetAllAsync(cancellationToken),
            "locations" => await _locationRepository.GetAllAsync(cancellationToken),
            "events" => await _eventRepository.GetAllAsync(cancellationToken),
            "relationships" => await _relationshipRepository.GetAllAsync(cancellationToken),
            _ => throw new ArgumentException($"Unknown entity type: {entityType}")
        };

        var json = JsonSerializer.Serialize(data, new JsonSerializerOptions
        {
            WriteIndented = true,
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase
        });

        return Encoding.UTF8.GetBytes(json);
    }

    private static string CsvEscape(string? value)
    {
        if (value == null) return "";
        if (value.Contains(',') || value.Contains('"') || value.Contains('\n'))
            return $"\"{value.Replace("\"", "\"\"")}\"";
        return value;
    }
}
