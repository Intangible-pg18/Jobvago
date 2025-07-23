namespace Jobvago.Api.Models;

public class Company
{
    public int ID { get; set; }
    public string Name { get; set; } = string.Empty;
    public string? WebsiteURL { get; set; }
}