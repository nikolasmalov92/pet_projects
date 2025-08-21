#include <iostream>
#include <cstdio>
#include <string>
#include <vector>

int main()
{
    std::vector<int> numbers = {1, 2, 3, 4, 5};
    numbers.push_back(6);
    for (int i = 0; i < numbers.size(); i++)
    {
        std::cout << "Element " << i << ": " << numbers[i] << std::endl;
    }
    return 0;

}

