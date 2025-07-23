namespace Jobvago.Api.Models;

public class Job
{
    public int ID { get; set; }
    public string JobTitle { get; set; } = string.Empty;
    public string? Description { get; set; }
    public decimal? MinSalary { get; set; }
    public decimal? MaxSalary { get; set; }
    public string? Currency { get; set; }
    public string OriginalUrl { get; set; } = string.Empty;
    public DateTime? PostedAt { get; set; }
    public bool IsRemote { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime LastSeenAt { get; set; }

    public int CompanyID { get; set; }
    public Company Company { get; set; } = null!;

    public int SourceID { get; set; }
    public Source Source { get; set; } = null!; 

    public ICollection<JobLocation> JobLocations { get; set; } = new List<JobLocation>();
    public ICollection<JobSkill> JobSkills { get; set; } = new List<JobSkill>();
}