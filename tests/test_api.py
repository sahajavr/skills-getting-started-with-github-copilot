"""
Tests for the High School Management System API
"""

import pytest
from fastapi.testclient import TestClient
from src.app import app, activities


@pytest.fixture
def client():
    """Create a test client"""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_activities():
    """Reset activities data before each test"""
    # Store original state
    original_activities = {
        name: {
            "description": details["description"],
            "schedule": details["schedule"],
            "max_participants": details["max_participants"],
            "participants": details["participants"].copy()
        }
        for name, details in activities.items()
    }
    
    yield
    
    # Restore original state after test
    for name, details in original_activities.items():
        if name in activities:
            activities[name]["participants"] = details["participants"].copy()


class TestRootEndpoint:
    """Tests for the root endpoint"""
    
    def test_root_redirects_to_index(self, client):
        """Test that root URL redirects to static index.html"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/static/index.html"


class TestGetActivities:
    """Tests for GET /activities endpoint"""
    
    def test_get_activities_success(self, client):
        """Test retrieving all activities"""
        response = client.get("/activities")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        assert len(data) > 0
        
        # Check structure of activities
        for name, details in data.items():
            assert "description" in details
            assert "schedule" in details
            assert "max_participants" in details
            assert "participants" in details
            assert isinstance(details["participants"], list)
    
    def test_get_activities_contains_expected_activities(self, client):
        """Test that response contains expected activities"""
        response = client.get("/activities")
        data = response.json()
        
        expected_activities = [
            "Soccer Team", "Basketball Club", "Drama Club", 
            "Art Studio", "Debate Team", "Science Olympiad",
            "Chess Club", "Programming Class", "Gym Class"
        ]
        
        for activity in expected_activities:
            assert activity in data


class TestSignupEndpoint:
    """Tests for POST /activities/{activity_name}/signup endpoint"""
    
    def test_signup_success(self, client):
        """Test successful signup for an activity"""
        response = client.post(
            "/activities/Soccer%20Team/signup?email=newstudent@mergington.edu"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "newstudent@mergington.edu" in data["message"]
        assert "Soccer Team" in data["message"]
        
        # Verify participant was added
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert "newstudent@mergington.edu" in activities_data["Soccer Team"]["participants"]
    
    def test_signup_activity_not_found(self, client):
        """Test signup for non-existent activity"""
        response = client.post(
            "/activities/Nonexistent%20Activity/signup?email=student@mergington.edu"
        )
        assert response.status_code == 404
        
        data = response.json()
        assert "detail" in data
        assert "Activity not found" in data["detail"]
    
    def test_signup_duplicate_registration(self, client):
        """Test that duplicate signup is rejected"""
        # First signup
        response1 = client.post(
            "/activities/Soccer%20Team/signup?email=alex@mergington.edu"
        )
        assert response1.status_code == 400
        
        data = response1.json()
        assert "detail" in data
        assert "already signed up" in data["detail"]
    
    def test_signup_with_special_characters_in_email(self, client):
        """Test signup with special characters in email"""
        response = client.post(
            "/activities/Drama%20Club/signup?email=student%2Btest@mergington.edu"
        )
        assert response.status_code == 200
        
        # Verify participant was added
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert "student+test@mergington.edu" in activities_data["Drama Club"]["participants"]


class TestUnregisterEndpoint:
    """Tests for DELETE /activities/{activity_name}/unregister endpoint"""
    
    def test_unregister_success(self, client):
        """Test successful unregistration from an activity"""
        # Verify participant is initially registered
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert "alex@mergington.edu" in activities_data["Soccer Team"]["participants"]
        
        # Unregister
        response = client.delete(
            "/activities/Soccer%20Team/unregister?email=alex@mergington.edu"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "alex@mergington.edu" in data["message"]
        assert "Soccer Team" in data["message"]
        
        # Verify participant was removed
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert "alex@mergington.edu" not in activities_data["Soccer Team"]["participants"]
    
    def test_unregister_activity_not_found(self, client):
        """Test unregister from non-existent activity"""
        response = client.delete(
            "/activities/Nonexistent%20Activity/unregister?email=student@mergington.edu"
        )
        assert response.status_code == 404
        
        data = response.json()
        assert "detail" in data
        assert "Activity not found" in data["detail"]
    
    def test_unregister_not_signed_up(self, client):
        """Test unregister when student is not signed up"""
        response = client.delete(
            "/activities/Soccer%20Team/unregister?email=notsignedup@mergington.edu"
        )
        assert response.status_code == 400
        
        data = response.json()
        assert "detail" in data
        assert "not signed up" in data["detail"]
    
    def test_unregister_and_signup_again(self, client):
        """Test that a student can signup again after unregistering"""
        # Unregister
        response1 = client.delete(
            "/activities/Basketball%20Club/unregister?email=james@mergington.edu"
        )
        assert response1.status_code == 200
        
        # Signup again
        response2 = client.post(
            "/activities/Basketball%20Club/signup?email=james@mergington.edu"
        )
        assert response2.status_code == 200
        
        # Verify participant is in the list
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert "james@mergington.edu" in activities_data["Basketball Club"]["participants"]


class TestActivityCapacity:
    """Tests for activity capacity management"""
    
    def test_multiple_signups_within_capacity(self, client):
        """Test multiple students can signup within capacity"""
        # Get current participant count
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        initial_count = len(activities_data["Chess Club"]["participants"])
        max_capacity = activities_data["Chess Club"]["max_participants"]
        
        # Calculate how many more can signup
        slots_available = max_capacity - initial_count
        
        # Signup multiple students
        for i in range(min(2, slots_available)):
            response = client.post(
                f"/activities/Chess%20Club/signup?email=newstudent{i}@mergington.edu"
            )
            assert response.status_code == 200
        
        # Verify participants were added
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        current_count = len(activities_data["Chess Club"]["participants"])
        assert current_count == initial_count + min(2, slots_available)


class TestEdgeCases:
    """Tests for edge cases and special scenarios"""
    
    def test_activity_names_with_spaces(self, client):
        """Test that activity names with spaces are handled correctly"""
        activities_with_spaces = [
            "Soccer Team", "Basketball Club", "Drama Club",
            "Art Studio", "Debate Team", "Science Olympiad",
            "Chess Club", "Programming Class", "Gym Class"
        ]
        
        for activity in activities_with_spaces:
            encoded_activity = activity.replace(" ", "%20")
            response = client.post(
                f"/activities/{encoded_activity}/signup?email=test@mergington.edu"
            )
            # Should either succeed or return 400 if already signed up
            assert response.status_code in [200, 400]
    
    def test_empty_participants_list(self, client):
        """Test activities can have empty participant lists"""
        # Find an activity with participants and unregister all
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        
        # Unregister all from Science Olympiad
        for participant in activities_data["Science Olympiad"]["participants"].copy():
            client.delete(
                f"/activities/Science%20Olympiad/unregister?email={participant}"
            )
        
        # Verify empty list
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert len(activities_data["Science Olympiad"]["participants"]) == 0
