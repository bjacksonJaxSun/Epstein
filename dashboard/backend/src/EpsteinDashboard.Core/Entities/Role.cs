namespace EpsteinDashboard.Core.Entities;

public class Role
{
    public long RoleId { get; set; }
    public string Name { get; set; } = string.Empty;
    public string? Description { get; set; }
    public int TierLevel { get; set; } // 0=Freemium, 1=Basic, 2=Premium, 3=Admin

    // Navigation properties
    public ICollection<UserRole> UserRoles { get; set; } = new List<UserRole>();
}
