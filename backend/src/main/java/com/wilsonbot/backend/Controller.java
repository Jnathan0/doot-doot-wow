package com.wilsonbot.backend;

// import com.wilsonbot.backend.model.Sound;
// import com.wilsonbot.backend.service.SoundService;

// import org.springframework.beans.factory.annotation.Autowired;
// import org.springframework.data.domain.Page;

// import org.springframework.web.bind.annotation.PathVariable;
// import org.springframework.web.bind.annotation.RequestMapping;
// import org.springframework.web.bind.annotation.GetMapping;
// import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import com.wilsonbot.backend.entity.Sound;
import com.wilsonbot.backend.repository.SoundRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;


@CrossOrigin(origins = "*")
@RestController
@RequestMapping("/api/v1/")
public class Controller {
    @Autowired
    private SoundRepository soundRepository;

	@GetMapping("/sounds")
	public List<Sound> getAllSounds() {
		return soundRepository.findAll();
	}

    @GetMapping("/sounds/{id}")
    public ResponseEntity<Sound> getSoundById(@PathVariable(value = "id") String id) {
        Sound sound = soundRepository.findBySoundId(id);
        return ResponseEntity.ok().body(sound);


    }

    // @PostMapping("/users")
    // public User createUser(@RequestBody User user) {
    //     return userRepository.save(user);
    // }

    // @PutMapping("/users/{id}")
    // public ResponseEntity<User> updateUser(@PathVariable(value = "id")
    //                      Long id, @RequestBody User userDto)
    //         throws ResourceNotFoundException {

    //     User user = userRepository.findById(id)
    //             .orElseThrow(() -> new ResourceNotFoundException
    //                     ("User not found for this id :: " + id));

    //     user.setEmailId(userDto.getEmailId());
    //     user.setLastName(userDto.getLastName());
    //     user.setFirstName(userDto.getFirstName());
    //     user.setId(id);
    //     final User updateUser = userRepository.save(user);
    //     return ResponseEntity.ok(updateUser);
    // }

    // @DeleteMapping("/users/{id}")
    // public Map<String, Boolean> deleteUser(@PathVariable(value = "id")
    //                  Long id) throws ResourceNotFoundException {
    //     User user = userRepository.findById(id)
    //             .orElseThrow(() -> new ResourceNotFoundException
    //                     ("User not found for this id :: " + id));

    //     userRepository.delete(user);
    //     Map<String, Boolean> response = new HashMap<>();
    //     response.put("deleted", Boolean.TRUE);
    //     return response;
    // }
}


// @RestController
// public class Controller {

// 	@Autowired
// 	private SoundService soundService;

// 	@GetMapping("/")
// 	public String index() {
// 		return "Greetings from Spring Boot!";
// 	}

// 	@GetMapping(path="sounds/{id}", produces="application/json")
//     public Sound getByName(@PathVariable("id") String sound_id){
//         return soundService. getByName(sound_id);
//     }

// }