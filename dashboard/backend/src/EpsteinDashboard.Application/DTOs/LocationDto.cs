namespace EpsteinDashboard.Application.DTOs;

public class LocationDto
{
    public long LocationId { get; set; }
    public string LocationName { get; set; } = string.Empty;
    public string? LocationType { get; set; }
    public string? StreetAddress { get; set; }
    public string? City { get; set; }
    public string? StateProvince { get; set; }
    public string? Country { get; set; }
    public string? PostalCode { get; set; }
    public double? Latitude { get; set; }
    public double? Longitude { get; set; }
    public string? OwnerName { get; set; }
    public string? Description { get; set; }
    public string? CreatedAt { get; set; }
    public string? UpdatedAt { get; set; }
}

public class LocationListDto
{
    public long LocationId { get; set; }
    public string LocationName { get; set; } = string.Empty;
    public string? LocationType { get; set; }
    public string? City { get; set; }
    public string? StateProvince { get; set; }
    public string? Country { get; set; }
    public double? GpsLatitude { get; set; }
    public double? GpsLongitude { get; set; }
    public string? Owner { get; set; }
    public string? Description { get; set; }
    public int EventCount { get; set; }
    public int MediaCount { get; set; }
    public int EvidenceCount { get; set; }
    public int TotalActivity { get; set; }
}
