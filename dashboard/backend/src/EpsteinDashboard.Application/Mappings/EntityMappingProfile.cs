using System.Text.Json;
using AutoMapper;
using EpsteinDashboard.Application.DTOs;
using EpsteinDashboard.Core.Entities;
using EpsteinDashboard.Core.Models;

namespace EpsteinDashboard.Application.Mappings;

public class EntityMappingProfile : Profile
{
    public EntityMappingProfile()
    {
        // Document
        CreateMap<Document, DocumentDto>();
        CreateMap<Document, DocumentListDto>();

        // Person
        CreateMap<Person, PersonDto>();
        CreateMap<Person, PersonListDto>();
        CreateMap<Person, PersonDetailDto>()
            .ForMember(dest => dest.Relationships, opt => opt.Ignore())
            .ForMember(dest => dest.RelationshipCount, opt => opt.Ignore())
            .ForMember(dest => dest.EventCount, opt => opt.Ignore())
            .ForMember(dest => dest.DocumentCount, opt => opt.Ignore())
            .ForMember(dest => dest.FinancialTransactionCount, opt => opt.Ignore())
            .ForMember(dest => dest.MediaCount, opt => opt.Ignore())
            .ForMember(dest => dest.NameVariations, opt => opt.MapFrom(src => ParseJsonArray(src.NameVariations)))
            .ForMember(dest => dest.Roles, opt => opt.MapFrom(src => ParseJsonArray(src.Roles)))
            .ForMember(dest => dest.EmailAddresses, opt => opt.MapFrom(src => ParseJsonArray(src.EmailAddresses)))
            .ForMember(dest => dest.PhoneNumbers, opt => opt.MapFrom(src => ParseJsonArray(src.PhoneNumbers)))
            .ForMember(dest => dest.Addresses, opt => opt.MapFrom(src => ParseJsonArray(src.Addresses)));

        // Organization
        CreateMap<Organization, OrganizationDto>()
            .ForMember(dest => dest.ParentOrganizationName,
                opt => opt.MapFrom(src => src.ParentOrganization != null ? src.ParentOrganization.OrganizationName : null));

        // Location
        CreateMap<Location, LocationDto>()
            .ForMember(dest => dest.OwnerName,
                opt => opt.MapFrom(src =>
                    src.OwnerPerson != null ? src.OwnerPerson.FullName :
                    src.OwnerOrganization != null ? src.OwnerOrganization.OrganizationName : null));

        // Event
        CreateMap<Event, EventDto>()
            .ForMember(dest => dest.LocationName,
                opt => opt.MapFrom(src => src.Location != null ? src.Location.LocationName : null));

        CreateMap<TimelineEntry, TimelineEventDto>();

        CreateMap<EventParticipant, EventParticipantDto>()
            .ForMember(dest => dest.PersonName,
                opt => opt.MapFrom(src => src.Person != null ? src.Person.FullName : null))
            .ForMember(dest => dest.OrganizationName,
                opt => opt.MapFrom(src => src.Organization != null ? src.Organization.OrganizationName : null));

        // Relationship
        CreateMap<Relationship, RelationshipDto>()
            .ForMember(dest => dest.Person1Name,
                opt => opt.MapFrom(src => src.Person1 != null ? src.Person1.FullName : null))
            .ForMember(dest => dest.Person2Name,
                opt => opt.MapFrom(src => src.Person2 != null ? src.Person2.FullName : null));

        // Communication
        CreateMap<Communication, CommunicationDto>()
            .ForMember(dest => dest.SenderName,
                opt => opt.MapFrom(src =>
                    src.SenderPerson != null ? src.SenderPerson.FullName :
                    src.SenderOrganization != null ? src.SenderOrganization.OrganizationName : null));

        CreateMap<CommunicationRecipient, CommunicationRecipientDto>()
            .ForMember(dest => dest.PersonName,
                opt => opt.MapFrom(src => src.Person != null ? src.Person.FullName : null))
            .ForMember(dest => dest.OrganizationName,
                opt => opt.MapFrom(src => src.Organization != null ? src.Organization.OrganizationName : null));

        // Financial
        CreateMap<FinancialTransaction, FinancialTransactionDto>()
            .ForMember(dest => dest.FromName,
                opt => opt.MapFrom(src =>
                    src.FromPerson != null ? src.FromPerson.FullName :
                    src.FromOrganization != null ? src.FromOrganization.OrganizationName : null))
            .ForMember(dest => dest.ToName,
                opt => opt.MapFrom(src =>
                    src.ToPerson != null ? src.ToPerson.FullName :
                    src.ToOrganization != null ? src.ToOrganization.OrganizationName : null));

        CreateMap<FinancialFlow, FinancialFlowDto>();
        CreateMap<SankeyNode, SankeyNodeDto>();
        CreateMap<SankeyLink, SankeyLinkDto>();

        // Media
        CreateMap<MediaFile, MediaFileDto>();
        CreateMap<ImageAnalysis, ImageAnalysisDto>();

        // Evidence
        CreateMap<EvidenceItem, EvidenceItemDto>()
            .ForMember(dest => dest.SeizedFromLocationName,
                opt => opt.MapFrom(src => src.SeizedFromLocation != null ? src.SeizedFromLocation.LocationName : null))
            .ForMember(dest => dest.SeizedFromPersonName,
                opt => opt.MapFrom(src => src.SeizedFromPerson != null ? src.SeizedFromPerson.FullName : null));

        // Search
        CreateMap<SearchResult, SearchResultDto>();

        // Network
        CreateMap<NetworkGraph, NetworkGraphDto>();
        CreateMap<NetworkNode, NetworkNodeDto>()
            .ForMember(dest => dest.NodeType,
                opt => opt.MapFrom(src => src.NodeType.ToString()));
        CreateMap<NetworkEdge, NetworkEdgeDto>();
    }

    private static List<string>? ParseJsonArray(string? jsonString)
    {
        if (string.IsNullOrWhiteSpace(jsonString))
            return null;

        try
        {
            var result = JsonSerializer.Deserialize<List<string>>(jsonString);
            return result?.Count > 0 ? result : null;
        }
        catch
        {
            // If it's not valid JSON, treat the string as a single item
            return new List<string> { jsonString };
        }
    }
}
